"""
Smart search orchestrator — efficient multi-source academic search.

Instead of calling 3-4 search tools manually and getting redundant results,
smart_search runs a single query through sources in priority order,
deduplicates by DOI, and stops early when coverage is sufficient.

find_paper resolves any identifier (DOI, PMID, title, arXiv ID, URL)
through the cheapest path without the caller needing to know which tool to use.
"""

import re
import logging
from typing import Any, Dict, List, Optional, Tuple

import cache
import openalex_client as oalex
import semantic_scholar_client as s2
import crossref_client as cr
import arxiv_client
import medrxiv_client

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
    cache_key = cache.make_key("smart_search", query, num_results, year, sources, include_preprints)
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        cached_result["from_cache"] = True
        return cached_result

    if sources is None:
        sources = ["openalex", "s2"]
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
        fetch_count = max(remaining + 5, overfetch if not sources_queried else remaining + 3)

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
            # Title search — use OpenAlex, take top result
            results = oalex.search_works(clean_id, num_results=1)
            if results:
                result = results[0]
                source = "openalex"

        # Fallback chain if primary didn't work
        if not result or (isinstance(result, dict) and "error" in result):
            if id_type == "doi":
                try:
                    result = cr.get_work_by_doi(clean_id)
                    source = "crossref"
                except Exception as e:
                    logger.debug(f"find_paper CrossRef fallback failed for {clean_id}: {e}")

            if not result or (isinstance(result, dict) and "error" in result):
                if id_type in ("doi", "pmid"):
                    prefix = "DOI:" if id_type == "doi" else "PMID:"
                    try:
                        result = s2.get_paper_details(f"{prefix}{clean_id}")
                        source = "s2"
                    except Exception as e:
                        logger.debug(f"find_paper S2 fallback failed for {prefix}{clean_id}: {e}")

                elif id_type == "title":
                    try:
                        results = s2.search_papers(clean_id, num_results=1)
                        if results:
                            result = results[0]
                            source = "s2"
                    except Exception as e:
                        logger.debug(f"find_paper S2 title fallback failed for '{clean_id}': {e}")

    except Exception as e:
        logger.warning(f"find_paper primary lookup failed: {e}")

    if not result or (isinstance(result, dict) and "error" in result):
        return {
            "error": f"Could not resolve identifier: {identifier}",
            "id_type_detected": id_type,
            "suggestion": "Try a different format or use a specific search tool.",
        }

    if isinstance(result, dict):
        result["resolved_via"] = source
        result["from_cache"] = False

    # Cache the result
    cache.put(cache_key, result, category="paper", ttl=cache.PAPER_TTL)

    return result


# --- Internal helpers ---

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
        match = re.search(r'(\d{4}\.\d{4,5}(?:v\d+)?)', text)
        if match:
            return ("arxiv", match.group(1))

    if "medrxiv.org/" in text or "biorxiv.org/" in text:
        match = re.search(r'(10\.1101/[\d.]+)', text)
        if match:
            return ("medrxiv_doi", match.group(1))

    if "pubmed.ncbi.nlm.nih.gov/" in text:
        match = re.search(r'/(\d+)', text)
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
    if re.match(r'^\d{4}\.\d{4,5}(v\d+)?$', text):
        return ("arxiv", text)

    # Raw PMID (all digits, 6-9 chars)
    if re.match(r'^\d{6,9}$', text):
        return ("pmid", text)

    # S2 paper ID (40-char hex)
    if re.match(r'^[0-9a-f]{40}$', text):
        return ("s2", text)

    # Default: treat as title search
    return ("title", text)
