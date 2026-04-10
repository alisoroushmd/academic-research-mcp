"""
Smart search orchestrator — efficient multi-source academic search.

Instead of calling 3-4 search tools manually and getting redundant results,
smart_search runs a single query through sources in priority order,
deduplicates by DOI, and stops early when coverage is sufficient.

find_paper resolves any identifier (DOI, PMID, title, arXiv ID, URL)
through the cheapest path without the caller needing to know which tool to use.
"""

import json
import re
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import cache
import http_client
import openalex_client as oalex
import semantic_scholar_client as s2
import crossref_client as cr
import arxiv_client
import medrxiv_client
import pubmed_client
from utils import title_similarity, has_medical_terms, _GENERIC_WORDS, _MEDICAL_TERMS

logger = logging.getLogger(__name__)


def smart_search(
    query: str,
    num_results: int = 10,
    year: Optional[str] = None,
    sources: Optional[List[str]] = None,
    include_preprints: bool = True,
    deduplicate: bool = True,
) -> Dict[str, Any]:
    """
    Efficient multi-source search with deduplication and early stopping.

    Strategy:
    1. Check cache first
    2. Query OpenAlex (fastest, broadest, no rate limit concerns)
    3. If coverage is thin (<50% of requested), add Semantic Scholar
    4. If preprints requested and coverage still thin, add arXiv/medRxiv
    5. CrossRef as final fallback only if still under target
    6. Deduplicate by DOI across all sources
    7. Cache the merged result

    Parameters:
        query: Search query.
        num_results: Target number of unique results (default: 10).
        year: Year filter (e.g., "2020-2025").
        sources: Override source priority. Default: ["openalex", "s2", "arxiv", "medrxiv", "crossref"].
                 Use this to force specific sources (e.g., ["arxiv"] for CS preprints only).
        include_preprints: Include arXiv/medRxiv in the search (default: True).
        deduplicate: Deduplicate by DOI (default: True).

    Returns:
        Dict with:
          - results: List of paper dicts (compact format)
          - sources_queried: Which APIs were actually called
          - total_raw: Total results before dedup
          - total_deduped: Results after dedup
          - from_cache: Whether the result came from cache
    """
    # Check cache
    cache_key = cache.make_key(
        "smart_search", query, num_results, year, sources, include_preprints
    )
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        cached_result["from_cache"] = True
        return cached_result

    if sources is None:
        sources = ["openalex"]
        if _has_medical_terms(query):
            sources.append("pubmed")
        sources.append("s2")
        if include_preprints:
            sources.extend(["arxiv", "medrxiv"])
        sources.append("crossref")

    all_papers = []
    sources_queried = []
    target = num_results

    # Fetch more than needed from first source to account for dedup
    overfetch = int(num_results * 1.5)

    for source in sources:
        # Early stopping: if we have enough unique results, skip remaining sources
        unique_count = len(_deduplicate(all_papers)) if deduplicate else len(all_papers)
        if unique_count >= target:
            break

        # How many more do we need?
        remaining = target - unique_count
        fetch_count = max(
            remaining + 5, overfetch if not sources_queried else remaining + 3
        )

        try:
            papers = _query_source(source, query, fetch_count, year)
            if papers:
                all_papers.extend(papers)
                sources_queried.append(source)
        except Exception as e:
            logger.warning(f"Source {source} failed: {e}")
            continue

        # After first source, reduce overfetch
        overfetch = remaining + 3

    total_raw = len(all_papers)

    # Deduplicate
    if deduplicate:
        results = _deduplicate(all_papers)
    else:
        results = all_papers

    # Trim to requested count
    results = results[:num_results]

    output = {
        "results": results,
        "sources_queried": sources_queried,
        "total_raw": total_raw,
        "total_deduped": len(results),
        "from_cache": False,
    }

    # Cache the result
    cache.put(cache_key, output, category="smart_search", ttl=cache.SEARCH_TTL)

    return output


def find_paper(identifier: str) -> Dict[str, Any]:
    """
    Resolve any paper identifier to full metadata through the cheapest path.

    Accepts:
    - DOI: "10.1038/s41591-023-02437-x" or "DOI:10.1038/..."
    - PMID: "37890456" or "PMID:37890456"
    - arXiv ID: "2312.00567" or "arXiv:2312.00567"
    - URL: any DOI, arXiv, medRxiv, bioRxiv, or PubMed URL
    - Title string: "Real-time semantic segmentation of gastric..."

    Resolution priority (cheapest first):
    1. Cache lookup
    2. DOI → OpenAlex (free, fast)
    3. PMID → OpenAlex (via pmid: prefix)
    4. arXiv ID → arXiv API (free, 3s rate limit)
    5. Title → OpenAlex search (single result)
    6. Fallback → Semantic Scholar, CrossRef

    Parameters:
        identifier: Any paper identifier or title string.

    Returns:
        Dict with paper metadata, or error message.
    """
    identifier = identifier.strip()

    # Check cache
    cache_key = cache.make_key("find_paper", identifier)
    cached = cache.get(cache_key)
    if cached is not None:
        cached["from_cache"] = True
        return cached

    # Classify the identifier
    id_type, clean_id = _classify_identifier(identifier)

    result = None
    source = None

    try:
        if id_type == "doi":
            # OpenAlex is fastest for DOI lookups
            result = oalex.get_work(f"doi:{clean_id}")
            source = "openalex"

        elif id_type == "pmid":
            # OpenAlex supports PMID lookups
            result = oalex.get_work(f"pmid:{clean_id}")
            source = "openalex"

        elif id_type == "arxiv":
            # arXiv API is the authority for arXiv papers
            result = arxiv_client.get_arxiv_paper(clean_id)
            source = "arxiv"

        elif id_type == "medrxiv_doi":
            # medRxiv API for preprint DOIs
            result = medrxiv_client.get_medrxiv_preprint(clean_id)
            source = "medrxiv"

        elif id_type == "s2":
            # Semantic Scholar ID
            result = s2.get_paper_details(clean_id)
            source = "s2"

        elif id_type == "title":
            # Title search — fetch multiple candidates and pick best match.
            # Natural language title strings (e.g. "Ebigbo real-time Barrett
            # deep learning") rarely match top-1; we need candidates + scoring.
            result, source = _resolve_title(clean_id)

        # Fallback chain if primary didn't work
        if not result or (isinstance(result, dict) and "error" in result):
            if id_type == "doi":
                try:
                    result = cr.get_work_by_doi(clean_id)
                    source = "crossref"
                except Exception as e:
                    logger.debug(
                        f"find_paper CrossRef fallback failed for {clean_id}: {e}"
                    )

            if not result or (isinstance(result, dict) and "error" in result):
                if id_type in ("doi", "pmid"):
                    prefix = "DOI:" if id_type == "doi" else "PMID:"
                    try:
                        result = s2.get_paper_details(f"{prefix}{clean_id}")
                        source = "s2"
                    except Exception as e:
                        logger.debug(
                            f"find_paper S2 fallback failed for {prefix}{clean_id}: {e}"
                        )

    except Exception as e:
        logger.warning(f"find_paper primary lookup failed: {e}")

    if not result or (isinstance(result, dict) and "error" in result):
        # Tailor the error to the identifier type — DOI/PMID failures get a
        # strong redirect because they almost always indicate a fabricated ID.
        if id_type in ("doi", "pmid"):
            return {
                "error": f"This {id_type.upper()} does not exist: {identifier}",
                "id_type_detected": id_type,
                "verified_against": ["openalex", "crossref", "semantic_scholar"],
                "action_required": (
                    "STOP. Do NOT guess another identifier. "
                    "Use smart_search or search_papers with the author name "
                    "and topic keywords to find the correct paper and its real DOI."
                ),
            }
        return {
            "error": f"Could not resolve identifier: {identifier}",
            "id_type_detected": id_type,
            "action_required": (
                "Use smart_search or search_papers with author name + topic "
                "keywords to find the paper. Do not guess identifiers."
            ),
        }

    if isinstance(result, dict):
        result["resolved_via"] = source
        result["from_cache"] = False

    # Cache the result
    cache.put(cache_key, result, category="paper", ttl=cache.PAPER_TTL)

    return result


# --- Internal helpers ---

# Keep underscore-prefixed aliases for backward compatibility within this module
_title_similarity = title_similarity
_has_medical_terms = has_medical_terms


def _resolve_title(title_query: str) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Resolve a natural-language title string to a paper by searching multiple
    sources, collecting all candidates, and picking the best match across
    all sources using cross-source DOI confirmation.
    Returns (result, source_name).
    """
    all_candidates: List[Tuple[Dict, str]] = []  # (paper, source_name)
    is_medical = _has_medical_terms(title_query)

    # Collect candidates from multiple sources in parallel-ish fashion
    for source_name, fetch_fn in [
        ("openalex", lambda: oalex.search_works(title_query, num_results=5)),
        (
            "s2",
            lambda: s2.search_papers(
                title_query,
                num_results=5,
                fields_of_study=["Medicine"] if is_medical else None,
            ),
        ),
        ("crossref", lambda: cr.search_works(title_query, num_results=5)),
    ]:
        try:
            results = fetch_fn()
            for r in results:
                all_candidates.append((r, source_name))
        except Exception as e:
            logger.debug(f"Title search via {source_name} failed: {e}")

    if not all_candidates:
        return None, None

    # Score all candidates
    scored = []
    for paper, src in all_candidates:
        title = paper.get("title", "") or ""
        base_score = _title_similarity(title_query, title)

        # Cross-source DOI confirmation: papers found by multiple sources
        # are more likely to be correct
        doi = _extract_doi(paper)
        if doi:
            doi_lower = doi.lower()
            appearances = sum(
                1
                for p, s in all_candidates
                if s != src and _extract_doi(p).lower() == doi_lower
            )
            if appearances > 0:
                base_score += 0.15 * appearances  # boost for cross-source confirmation

        scored.append((paper, src, base_score))

    scored.sort(key=lambda x: x[2], reverse=True)
    best_paper, best_source, best_score = scored[0]

    if best_score >= 0.20:
        return best_paper, best_source

    return None, None


def _query_source(
    source: str, query: str, num_results: int, year: Optional[str]
) -> List[Dict[str, Any]]:
    """Query a single source and return normalized results."""
    if source == "openalex":
        return oalex.search_works(query, num_results=num_results, year=year)
    elif source == "s2":
        return s2.search_papers(query, num_results=num_results, year=year)
    elif source == "crossref":
        return cr.search_works(query, num_results=num_results, year=year)
    elif source == "arxiv":
        return arxiv_client.search_arxiv(query, num_results=min(num_results, 20))
    elif source == "medrxiv":
        return medrxiv_client.search_medrxiv(query, num_results=min(num_results, 20))
    elif source == "pubmed":
        result = pubmed_client.search_pubmed(query, max_results=num_results)
        return result.get("papers", [])
    else:
        return []


def _deduplicate(papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicate papers by DOI. When duplicates exist, keep the version
    with the most metadata (highest field count). For papers without DOIs,
    deduplicate by normalized title prefix.
    """
    seen_dois = {}
    no_doi = []
    seen_title_prefixes = set()

    for paper in papers:
        doi = _extract_doi(paper)
        if doi:
            doi_lower = doi.lower()
            if doi_lower in seen_dois:
                existing = seen_dois[doi_lower]
                if _richness(paper) > _richness(existing):
                    seen_dois[doi_lower] = paper
            else:
                seen_dois[doi_lower] = paper
        else:
            title = (paper.get("title", "") or "").lower().strip()
            if not title:
                continue
            # Use first 80 chars as a fast dedup key (O(1) lookup)
            prefix = title[:80]
            if prefix not in seen_title_prefixes:
                seen_title_prefixes.add(prefix)
                no_doi.append(paper)

    return list(seen_dois.values()) + no_doi


def _extract_doi(paper: Dict) -> str:
    """Extract DOI from a paper dict, handling different field names."""
    doi = paper.get("doi", "")
    if not doi:
        # Check external_ids for S2 format
        ext_ids = paper.get("externalIds", {}) or {}
        doi = ext_ids.get("DOI", "")
    if doi:
        doi = doi.replace("https://doi.org/", "").strip()
    return doi


def _richness(paper: Dict) -> int:
    """Score how much metadata a paper dict contains."""
    score = 0
    for key, value in paper.items():
        if value:
            if isinstance(value, str) and len(value) > 10:
                score += 2
            elif isinstance(value, list) and len(value) > 0:
                score += 2
            else:
                score += 1
    return score


def _classify_identifier(identifier: str) -> Tuple[str, str]:
    """
    Classify an identifier string and return (type, cleaned_id).

    Returns one of: "doi", "pmid", "arxiv", "medrxiv_doi", "s2", "title"
    """
    text = identifier.strip()

    # URL patterns
    if "doi.org/" in text:
        doi = text.split("doi.org/", 1)[1].strip()
        return ("doi", doi)

    if "arxiv.org/" in text:
        match = re.search(r"(\d{4}\.\d{4,5}(?:v\d+)?)", text)
        if match:
            return ("arxiv", match.group(1))

    if "medrxiv.org/" in text or "biorxiv.org/" in text:
        match = re.search(r"(10\.1101/[\d.]+)", text)
        if match:
            return ("medrxiv_doi", match.group(1))

    if "pubmed.ncbi.nlm.nih.gov/" in text:
        match = re.search(r"/(\d+)", text)
        if match:
            return ("pmid", match.group(1))

    if "semanticscholar.org/paper/" in text:
        paper_id = text.split("/paper/", 1)[1].split("?")[0].split("/")[0]
        return ("s2", paper_id)

    # Prefix patterns
    if text.upper().startswith("DOI:"):
        return ("doi", text[4:].strip())

    if text.upper().startswith("PMID:"):
        return ("pmid", text[5:].strip())

    if text.upper().startswith("ARXIV:"):
        return ("arxiv", text[6:].strip())

    # Raw DOI (starts with 10.)
    if text.startswith("10."):
        if "10.1101/" in text:
            return ("medrxiv_doi", text)
        return ("doi", text)

    # Raw arXiv ID
    if re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", text):
        return ("arxiv", text)

    # Raw PMID (all digits, 6-9 chars)
    if re.match(r"^\d{6,9}$", text):
        return ("pmid", text)

    # S2 paper ID (40-char hex)
    if re.match(r"^[0-9a-f]{40}$", text):
        return ("s2", text)

    # Default: treat as title search
    return ("title", text)


def harvest_citations(
    seed_paper_ids: List[str],
    direction: str = "both",
) -> Dict[str, Any]:
    """
    Harvest citations and/or references from seed papers and deduplicate
    within the harvested set (synchronous version).

    Does NOT interact with review state — the caller (server.py) handles
    review logging and paper addition.
    """
    if len(seed_paper_ids) > 50:
        return {"error": "Maximum 50 seed papers per snowball search."}

    all_candidates = []
    has_api_key = bool(http_client.get_env("S2_API_KEY"))
    delay = 0.01 if has_api_key else 1.0

    for seed_id in seed_paper_ids:
        if direction in ("forward", "both"):
            try:
                citations = s2.get_paper_citations(seed_id, num_results=100)
                all_candidates.extend(citations)
            except Exception as e:
                logger.warning(f"Snowball citations failed for {seed_id}: {e}")

        if direction in ("backward", "both"):
            try:
                references = s2.get_paper_references(seed_id, num_results=100)
                all_candidates.extend(references)
            except Exception as e:
                logger.warning(f"Snowball references failed for {seed_id}: {e}")

        time.sleep(delay)

    total_harvested = len(all_candidates)
    deduped = _deduplicate(all_candidates)
    duplicates_within = total_harvested - len(deduped)

    return {
        "seed_count": len(seed_paper_ids),
        "candidates": deduped,
        "total_harvested": total_harvested,
        "duplicates_within_snowball": duplicates_within,
    }


async def async_harvest_citations(
    seed_paper_ids: List[str],
    direction: str = "both",
) -> Dict[str, Any]:
    """
    Async version of harvest_citations — processes seeds in parallel using
    asyncio.to_thread for each S2 API call. With S2_API_KEY (100 req/sec),
    50 seeds × 2 directions completes in ~2s instead of ~100s sequential.
    """
    import asyncio

    if len(seed_paper_ids) > 50:
        return {"error": "Maximum 50 seed papers per snowball search."}

    async def _fetch_seed(seed_id: str) -> List[Dict]:
        papers = []
        if direction in ("forward", "both"):
            try:
                cites = await asyncio.to_thread(s2.get_paper_citations, seed_id, 100)
                papers.extend(cites)
            except Exception as e:
                logger.warning(f"Snowball citations failed for {seed_id}: {e}")
        if direction in ("backward", "both"):
            try:
                refs = await asyncio.to_thread(s2.get_paper_references, seed_id, 100)
                papers.extend(refs)
            except Exception as e:
                logger.warning(f"Snowball references failed for {seed_id}: {e}")
        return papers

    # Process all seeds concurrently
    results = await asyncio.gather(*[_fetch_seed(sid) for sid in seed_paper_ids])

    all_candidates = []
    for papers in results:
        all_candidates.extend(papers)

    total_harvested = len(all_candidates)
    deduped = _deduplicate(all_candidates)
    duplicates_within = total_harvested - len(deduped)

    return {
        "seed_count": len(seed_paper_ids),
        "candidates": deduped,
        "total_harvested": total_harvested,
        "duplicates_within_snowball": duplicates_within,
    }
