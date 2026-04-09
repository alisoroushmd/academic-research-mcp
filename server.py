"""
Academic Research MCP Server

A unified MCP server providing access to seven academic research APIs
plus Unpaywall PDF resolution, local caching, and batch operations:

  1. Google Scholar -- keyword search, advanced search, author profiles
  2. ORCID -- researcher profiles, publications, employment, education, funding
  3. Semantic Scholar -- paper search, citation graphs, author metrics, recommendations, batch lookup
  4. arXiv -- CS/ML preprints, search by author/title/category, full metadata
  5. medRxiv/bioRxiv -- health sciences preprints, publication status tracking
  6. OpenAlex -- 250M+ works, highest throughput, no auth needed
  7. CrossRef -- DOI registry fallback, 50 req/sec, comprehensive metadata
  8. Unpaywall -- legal open access PDF resolution for any DOI

Features:
  - Consolidated tool surface (~18 tools instead of 39)
  - Local SQLite cache to avoid redundant API calls
  - S2 batch endpoint for up to 500 papers in one request
  - CrossRef fallback when other APIs are rate-limited

No API keys required for basic use. Optional env vars:
  - S2_API_KEY: Higher Semantic Scholar rate limits
  - OPENALEX_EMAIL: OpenAlex polite pool (10 req/sec vs 1 req/sec)
  - CROSSREF_EMAIL: CrossRef polite pool (50 req/sec)
"""

from typing import Any, Dict, List, Literal, Optional
import asyncio
import logging
import re

from mcp.server.fastmcp import FastMCP

from google_scholar_web_search import google_scholar_search, advanced_google_scholar_search
from scholarly import scholarly
import orcid_client
import semantic_scholar_client as s2
import arxiv_client
import medrxiv_client
import openalex_client as oalex
import crossref_client as cr
import unpaywall_client as unpaywall
import orchestrator
import cache

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ============================================================================
# TOKEN OPTIMIZATION: Compact output mode
# ============================================================================

def _compact_paper(paper: Dict[str, Any]) -> Dict[str, Any]:
    """
    Strip a paper result to essential fields for minimal token usage.
    Reduces output by ~60-70% compared to full results.
    """
    # Truncate abstract to 150 chars
    abstract = paper.get("abstract", "") or ""
    if len(abstract) > 150:
        abstract = abstract[:150].rsplit(" ", 1)[0] + "..."

    # Truncate authors to first 3
    authors = paper.get("authors", [])
    if isinstance(authors, str):
        authors_short = authors[:100] + ("..." if len(authors) > 100 else "")
    elif isinstance(authors, list):
        if len(authors) > 3:
            authors_short = authors[:3] + [f"+{len(authors)-3} more"]
        else:
            authors_short = authors
    else:
        authors_short = authors

    compact = {
        "title": paper.get("title", ""),
        "authors": authors_short,
        "year": paper.get("year") or paper.get("publication_year"),
        "cited_by": paper.get("citation_count") or paper.get("cited_by_count") or paper.get("citedby", 0),
        "doi": paper.get("doi", ""),
    }

    # Only include abstract snippet if it exists
    if abstract:
        compact["abstract_snippet"] = abstract

    # Include OA URL if available
    oa_url = paper.get("open_access_url") or paper.get("pdf_url", "")
    if oa_url:
        compact["pdf_url"] = oa_url

    return compact


def _compact_list(papers: list, brief: bool) -> list:
    """Apply compact mode to a list of papers if brief=True."""
    if not brief:
        return papers
    return [_compact_paper(p) if isinstance(p, dict) and "error" not in p else p for p in papers]


def _compact_single(paper: dict, brief: bool) -> dict:
    """Apply compact mode to a single paper if brief=True."""
    if not brief or not isinstance(paper, dict) or "error" in paper:
        return paper
    return _compact_paper(paper)


# ============================================================================
# ERROR HELPERS: Consistent error returns
# ============================================================================

def _error_dict(msg: str) -> Dict[str, Any]:
    """Return a standard error dict for single-result tools."""
    return {"error": msg}


def _error_list(msg: str) -> List[Dict[str, Any]]:
    """Return a standard error list for multi-result tools."""
    return [{"error": msg}]


# ============================================================================
# VALIDATION HELPERS
# ============================================================================

_VALID_SOURCES = {"openalex", "s2", "crossref", "arxiv", "medrxiv", "google_scholar", "orcid"}
_ORCID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")


def _validate_orcid(orcid_id: str) -> Optional[str]:
    """Validate ORCID format, return error message or None."""
    if not _ORCID_RE.match(orcid_id.strip()):
        return f"Invalid ORCID format: '{orcid_id}'. Expected DDDD-DDDD-DDDD-DDDD."
    return None


def _clamp(value: int, low: int, high: int) -> int:
    """Clamp an integer to [low, high]."""
    return max(low, min(value, high))


mcp = FastMCP("academic-research")


# ============================================================================
# SMART SEARCH & UNIVERSAL RESOLVER (use these first)
# ============================================================================

@mcp.tool()
async def smart_search(
    query: str,
    num_results: int = 10,
    year: Optional[str] = None,
    sources: Optional[List[str]] = None,
    include_preprints: bool = True,
    brief: bool = True,
) -> Dict[str, Any]:
    """
    THE RECOMMENDED SEARCH TOOL. Efficiently searches multiple academic databases
    with automatic deduplication and early stopping. Use this instead of calling
    individual search tools -- it picks the best sources, avoids redundant queries,
    and deduplicates results by DOI.

    Search priority: OpenAlex (fast, broad) -> Semantic Scholar (AI/ML strength)
    -> arXiv + medRxiv (preprints) -> CrossRef (fallback). Stops early when
    enough unique results are found.

    Args:
        query: Search query (e.g., "gastric intestinal metaplasia deep learning")
        num_results: Target number of unique results (default: 10, max: 100)
        year: Year filter (e.g., "2020-2025")
        sources: Override source order (e.g., ["arxiv", "s2"] for CS preprints).
                 Options: "openalex", "s2", "crossref", "arxiv", "medrxiv"
        include_preprints: Include arXiv/medRxiv (default: True)
        brief: Return compact results (default: True)
    """
    num_results = _clamp(num_results, 1, 100)
    logger.info(f"Smart search: {query}")
    try:
        result = await asyncio.to_thread(
            orchestrator.smart_search, query, num_results, year, sources, include_preprints
        )
        if brief:
            result["results"] = _compact_list(result.get("results", []), True)
        return result
    except Exception as e:
        return _error_dict(f"Smart search failed: {str(e)}")


@mcp.tool()
async def find_paper(identifier: str, brief: bool = False) -> Dict[str, Any]:
    """
    Universal paper resolver. Give it ANY identifier and it finds the paper
    through the cheapest API path. No need to figure out which tool to use.

    Accepts: DOI, PMID, arXiv ID, medRxiv DOI, Semantic Scholar ID,
    PubMed/arXiv/DOI URLs, or even a title string.

    Examples:
        "10.1038/s41591-023-02437-x"
        "PMID:37890456"
        "2312.00567"
        "https://arxiv.org/abs/2312.00567"
        "Real-time semantic segmentation of gastric intestinal metaplasia"

    Args:
        identifier: Any paper identifier, URL, or title
        brief: Return compact result (default: False for single lookups)
    """
    logger.info(f"Find paper: {identifier}")
    try:
        result = await asyncio.to_thread(orchestrator.find_paper, identifier)
        return _compact_single(result, brief)
    except Exception as e:
        return _error_dict(f"Find paper failed: {str(e)}")


# ============================================================================
# UNIFIED SEARCH TOOLS
# ============================================================================

@mcp.tool()
async def search_papers(
    query: str,
    source: Optional[str] = None,
    num_results: int = 10,
    year: Optional[str] = None,
    brief: bool = True,
    # Source-specific options
    fields_of_study: Optional[List[str]] = None,
    open_access_only: bool = False,
    sort_by: Optional[str] = None,
    category: Optional[str] = None,
    type_filter: Optional[str] = None,
    author: Optional[str] = None,
    year_range: Optional[tuple] = None,
    server: Literal["medrxiv", "biorxiv"] = "medrxiv",
) -> List[Dict[str, Any]]:
    """
    Search for papers across any academic database. If no source is specified,
    uses smart_search (recommended). Specify a source when you need
    source-specific features.

    Args:
        query: Search query
        source: API to search. Options: "openalex", "s2", "crossref", "arxiv",
                "medrxiv", "google_scholar". Default: None (uses smart_search).
        num_results: Number of results (default: 10, max: 200)
        year: Year filter (e.g., "2020-2025")
        brief: Return compact results (default: True)
        fields_of_study: [S2 only] Filter by field (e.g., ["Medicine", "Computer Science"])
        open_access_only: [S2, OpenAlex] Only return open-access papers
        sort_by: Sort order. OpenAlex: "relevance_score"|"cited_by_count"|"publication_date".
                 arXiv: "relevance"|"lastUpdatedDate"|"submittedDate".
                 CrossRef: "relevance"|"published"|"is-referenced-by-count".
        category: [arXiv] Filter by category (e.g., "cs.CV", "cs.AI")
        type_filter: [CrossRef] Filter by type (e.g., "journal-article")
        author: [Google Scholar] Author name filter
        year_range: [Google Scholar] Tuple of (start_year, end_year)
        server: [medRxiv/bioRxiv] Which server to search (default: "medrxiv")
    """
    num_results = _clamp(num_results, 1, 200)
    logger.info(f"Search papers: query={query}, source={source}")

    try:
        if source is None:
            result = await asyncio.to_thread(
                orchestrator.smart_search, query, num_results, year
            )
            return _compact_list(result.get("results", []), brief)

        if source == "openalex":
            results = await asyncio.to_thread(
                oalex.search_works, query, min(num_results, 200), year,
                open_access_only, sort_by or "relevance_score"
            )
        elif source == "s2":
            results = await asyncio.to_thread(
                s2.search_papers, query, min(num_results, 100), year,
                fields_of_study, open_access_only
            )
        elif source == "crossref":
            results = await asyncio.to_thread(
                cr.search_works, query, min(num_results, 100), year,
                sort_by or "relevance", type_filter
            )
        elif source == "arxiv":
            results = await asyncio.to_thread(
                arxiv_client.search_arxiv, query, min(num_results, 100),
                sort_by or "relevance", category
            )
        elif source == "medrxiv":
            results = await asyncio.to_thread(
                medrxiv_client.search_medrxiv, query, num_results, server
            )
        elif source == "google_scholar":
            if author or year_range:
                results = await asyncio.to_thread(
                    advanced_google_scholar_search, query, author, year_range, num_results
                )
            else:
                results = await asyncio.to_thread(
                    google_scholar_search, query, num_results
                )
        else:
            return _error_list(
                f"Unknown source: '{source}'. "
                f"Options: openalex, s2, crossref, arxiv, medrxiv, google_scholar"
            )

        return _compact_list(results, brief)
    except Exception as e:
        return _error_list(f"Search failed ({source or 'smart'}): {str(e)}")


@mcp.tool()
async def search_authors(
    query: str,
    source: Optional[str] = None,
    num_results: int = 5,
) -> List[Dict[str, Any]]:
    """
    Search for researchers/authors across academic databases.

    Args:
        query: Author name or affiliation (e.g., "Ali Soroush", "Mount Sinai gastroenterology")
        source: API to search. Options: "openalex" (default), "s2", "orcid",
                "google_scholar". Default: tries OpenAlex first.
        num_results: Number of results (default: 5, max: 50)
    """
    num_results = _clamp(num_results, 1, 50)
    source = source or "openalex"
    logger.info(f"Search authors: query={query}, source={source}")

    try:
        if source == "openalex":
            return await asyncio.to_thread(oalex.search_authors, query, num_results)
        elif source == "s2":
            return await asyncio.to_thread(s2.search_authors, query, num_results)
        elif source == "orcid":
            return await asyncio.to_thread(orcid_client.search_orcid, query, num_results)
        elif source == "google_scholar":
            try:
                search_query = scholarly.search_author(query)
                author = await asyncio.to_thread(next, search_query)
                filled = await asyncio.to_thread(scholarly.fill, author)
                return [{
                    "name": filled.get("name", ""),
                    "affiliation": filled.get("affiliation", ""),
                    "interests": filled.get("interests", []),
                    "citedby": filled.get("citedby", 0),
                    "h_index": filled.get("hindex", 0),
                    "i10_index": filled.get("i10index", 0),
                    "publications": [
                        {
                            "title": pub.get("bib", {}).get("title", ""),
                            "year": pub.get("bib", {}).get("pub_year", ""),
                            "citations": pub.get("num_citations", 0),
                        }
                        for pub in filled.get("publications", [])[:10]
                    ],
                }]
            except StopIteration:
                return _error_list(f"No Google Scholar author found for: {query}")
        else:
            return _error_list(
                f"Unknown source: '{source}'. Options: openalex, s2, orcid, google_scholar"
            )
    except Exception as e:
        return _error_list(f"Author search failed ({source}): {str(e)}")


@mcp.tool()
async def get_author(
    identifier: str,
    source: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get a detailed author/researcher profile by ID.

    Args:
        identifier: Author ID. OpenAlex: "A5023888391" or ORCID. S2: author ID.
                    ORCID: "0000-0002-1234-5678".
        source: API to use. Options: "openalex" (default), "s2", "orcid".
                Auto-detected from identifier format when possible.
    """
    identifier = identifier.strip()
    logger.info(f"Get author: {identifier}, source={source}")

    # Auto-detect source from identifier format
    if source is None:
        if _ORCID_RE.match(identifier):
            source = "orcid"
        elif identifier.startswith("A") and identifier[1:].isdigit():
            source = "openalex"
        else:
            source = "s2"

    try:
        if source == "openalex":
            return await asyncio.to_thread(oalex.get_author, identifier)
        elif source == "s2":
            return await asyncio.to_thread(s2.get_author_details, identifier)
        elif source == "orcid":
            err = _validate_orcid(identifier)
            if err:
                return _error_dict(err)
            return await asyncio.to_thread(orcid_client.get_orcid_profile, identifier)
        else:
            return _error_dict(
                f"Unknown source: '{source}'. Options: openalex, s2, orcid"
            )
    except Exception as e:
        return _error_dict(f"Author lookup failed ({source}): {str(e)}")


@mcp.tool()
async def get_author_works(
    identifier: str,
    source: Optional[str] = None,
    num_results: int = 20,
    sort_by: Optional[str] = None,
    query: Optional[str] = None,
    category: Optional[str] = None,
    brief: bool = True,
) -> List[Dict[str, Any]]:
    """
    Get publications by a specific author.

    Args:
        identifier: Author ID or name depending on source.
                    OpenAlex: author ID or ORCID. S2: author ID. ORCID: "0000-0002-1234-5678".
                    CrossRef/arXiv: author name string.
        source: API to use. Options: "openalex" (default), "s2", "orcid",
                "crossref", "arxiv". Auto-detected from ID format when possible.
        num_results: Number of works (default: 20, max: 200)
        sort_by: [OpenAlex] "publication_date" or "cited_by_count"
        query: [CrossRef] Additional topic filter
        category: [arXiv] Category filter (e.g., "cs.CV")
        brief: Return compact results (default: True)
    """
    num_results = _clamp(num_results, 1, 200)
    identifier = identifier.strip()
    logger.info(f"Get author works: {identifier}, source={source}")

    # Auto-detect source from identifier format
    if source is None:
        if _ORCID_RE.match(identifier):
            source = "orcid"
        elif identifier.startswith("A") and identifier[1:].isdigit():
            source = "openalex"
        elif identifier.isdigit():
            source = "s2"
        else:
            source = "crossref"

    try:
        if source == "openalex":
            results = await asyncio.to_thread(
                oalex.get_author_works, identifier, num_results,
                sort_by or "publication_date"
            )
        elif source == "s2":
            results = await asyncio.to_thread(
                s2.get_author_papers, identifier, min(num_results, 100)
            )
        elif source == "orcid":
            err = _validate_orcid(identifier)
            if err:
                return _error_list(err)
            results = await asyncio.to_thread(
                orcid_client.get_orcid_works, identifier, num_results
            )
        elif source == "crossref":
            results = await asyncio.to_thread(
                cr.search_by_author, identifier, query, min(num_results, 100)
            )
        elif source == "arxiv":
            results = await asyncio.to_thread(
                arxiv_client.get_arxiv_by_author, identifier,
                min(num_results, 100), category
            )
        else:
            return _error_list(
                f"Unknown source: '{source}'. Options: openalex, s2, orcid, crossref, arxiv"
            )
        return _compact_list(results, brief)
    except Exception as e:
        return _error_list(f"Author works lookup failed ({source}): {str(e)}")


# ============================================================================
# ORCID-SPECIFIC TOOLS (unique capabilities not covered by unified tools)
# ============================================================================

@mcp.tool()
async def get_author_funding(orcid_id: str) -> List[Dict[str, Any]]:
    """
    Get funding/grants from an ORCID profile: funder, title, dates, grant number.
    Only available via ORCID.

    Args:
        orcid_id: ORCID iD (e.g., "0000-0002-1234-5678")
    """
    err = _validate_orcid(orcid_id)
    if err:
        return _error_list(err)
    logger.info(f"ORCID funding: {orcid_id}")
    try:
        return await asyncio.to_thread(orcid_client.get_orcid_funding, orcid_id)
    except Exception as e:
        return _error_list(f"ORCID funding lookup failed: {str(e)}")


# ============================================================================
# SEMANTIC SCHOLAR-SPECIFIC TOOLS (unique capabilities)
# ============================================================================

@mcp.tool()
async def get_paper_citations(paper_id: str, num_results: int = 20) -> List[Dict[str, Any]]:
    """
    Get papers that cite a given paper (forward citation graph). Useful for finding
    who built on a specific study. Powered by Semantic Scholar.

    Args:
        paper_id: Paper identifier (S2 ID, "DOI:...", "PMID:...", or arXiv ID)
        num_results: Number of citing papers (default: 20, max: 100)
    """
    num_results = _clamp(num_results, 1, 100)
    logger.info(f"Citations for: {paper_id}")
    try:
        return await asyncio.to_thread(s2.get_paper_citations, paper_id, num_results)
    except Exception as e:
        return _error_list(f"Citations lookup failed: {str(e)}")


@mcp.tool()
async def get_paper_references(paper_id: str, num_results: int = 20) -> List[Dict[str, Any]]:
    """
    Get papers referenced by a given paper (backward citation graph). Useful for
    tracing the intellectual lineage of a study. Powered by Semantic Scholar.

    Args:
        paper_id: Paper identifier (S2 ID, "DOI:...", "PMID:...", or arXiv ID)
        num_results: Number of referenced papers (default: 20, max: 100)
    """
    num_results = _clamp(num_results, 1, 100)
    logger.info(f"References for: {paper_id}")
    try:
        return await asyncio.to_thread(s2.get_paper_references, paper_id, num_results)
    except Exception as e:
        return _error_list(f"References lookup failed: {str(e)}")


@mcp.tool()
async def recommend_papers(paper_id: str, num_results: int = 10) -> List[Dict[str, Any]]:
    """
    Get paper recommendations based on a specific paper. Useful for discovering
    related work you might have missed. Powered by Semantic Scholar.

    Args:
        paper_id: Paper ID to base recommendations on
        num_results: Number of recommendations (default: 10, max: 100)
    """
    num_results = _clamp(num_results, 1, 100)
    logger.info(f"Recommendations for: {paper_id}")
    try:
        return await asyncio.to_thread(s2.get_recommended_papers, paper_id, num_results)
    except Exception as e:
        return _error_list(f"Recommendations failed: {str(e)}")


@mcp.tool()
async def batch_get_papers(paper_ids: List[str]) -> List[Optional[Dict[str, Any]]]:
    """
    Get details for up to 500 papers in a single request. Dramatically faster
    than individual lookups when processing reference lists, citation sets, or
    systematic review results. Powered by Semantic Scholar.

    Accepts any mix of identifiers: S2 IDs, DOIs (prefix "DOI:"),
    PMIDs (prefix "PMID:"), or ArXiv IDs.

    Args:
        paper_ids: List of paper identifiers (max 500)
    """
    logger.info(f"Batch lookup: {len(paper_ids)} papers")
    try:
        return await asyncio.to_thread(s2.batch_get_papers, paper_ids)
    except Exception as e:
        return _error_list(f"Batch lookup failed: {str(e)}")


# ============================================================================
# MEDRXIV/BIORXIV-SPECIFIC TOOLS (unique capabilities)
# ============================================================================

@mcp.tool()
async def preprints_by_date(
    start_date: str,
    end_date: str,
    server: Literal["medrxiv", "biorxiv"] = "medrxiv",
    num_results: int = 30,
) -> List[Dict[str, Any]]:
    """
    Get preprints posted within a date range. Useful for monitoring new work.

    Args:
        start_date: Start date "YYYY-MM-DD"
        end_date: End date "YYYY-MM-DD"
        server: "medrxiv" or "biorxiv"
        num_results: Max results (default: 30, max: 200)
    """
    num_results = _clamp(num_results, 1, 200)
    logger.info(f"{server} by date: {start_date} to {end_date}")
    try:
        return await asyncio.to_thread(
            medrxiv_client.search_medrxiv_by_date, start_date, end_date, server, num_results
        )
    except Exception as e:
        return _error_list(f"{server} date search failed: {str(e)}")


@mcp.tool()
async def preprint_status(doi: str) -> Dict[str, Any]:
    """
    Check whether a preprint has been published in a peer-reviewed journal.
    Returns the journal DOI, journal name, and publication date if published.

    Args:
        doi: Preprint DOI (e.g., "10.1101/2024.01.15.24301234")
    """
    logger.info(f"Publication status check: {doi}")
    try:
        return await asyncio.to_thread(medrxiv_client.get_publication_status, doi)
    except Exception as e:
        return _error_dict(f"Publication status check failed: {str(e)}")


@mcp.tool()
async def recent_preprints(
    category: str,
    server: Literal["medrxiv", "biorxiv"] = "medrxiv",
    num_results: int = 20,
) -> List[Dict[str, Any]]:
    """
    Get recent preprints in a specific subject category. Useful for staying
    current in your field.

    Args:
        category: Subject area (medRxiv: "gastroenterology", "oncology",
                  "health informatics", "epidemiology", "pathology",
                  "radiology and imaging". bioRxiv: "bioinformatics",
                  "cancer biology", "genomics", "systems biology")
        server: "medrxiv" or "biorxiv"
        num_results: Max results (default: 20, max: 100)
    """
    num_results = _clamp(num_results, 1, 100)
    logger.info(f"{server} recent in category: {category}")
    try:
        return await asyncio.to_thread(
            medrxiv_client.get_recent_by_category, category, server, num_results
        )
    except Exception as e:
        return _error_list(f"{server} category search failed: {str(e)}")


# ============================================================================
# OPENALEX-SPECIFIC TOOLS (unique capabilities)
# ============================================================================

@mcp.tool()
async def get_institution(institution_id: str) -> Dict[str, Any]:
    """
    Get institution details from OpenAlex: name, country, type, works count.

    Args:
        institution_id: OpenAlex institution ID or ROR ID
    """
    logger.info(f"OpenAlex institution: {institution_id}")
    try:
        return await asyncio.to_thread(oalex.get_institution, institution_id)
    except Exception as e:
        return _error_dict(f"Institution lookup failed: {str(e)}")


# ============================================================================
# UNPAYWALL / PDF RESOLUTION TOOLS
# ============================================================================

@mcp.tool()
async def find_paper_pdf(doi: str, verbose: bool = False) -> Dict[str, Any]:
    """
    Find the best available legal PDF for a paper by DOI. Checks Unpaywall,
    PubMed Central, preprint servers, and institutional repositories.

    Returns the PDF URL if available, or the best alternative (publisher
    landing page, preprint version). If no open access version exists,
    suggests checking institutional access.

    Args:
        doi: DOI string (e.g., "10.1038/s41591-023-02437-x" or
             "DOI:10.1016/j.gie.2023.06.056")
        verbose: Include all OA locations in response (default: False to save tokens)
    """
    logger.info(f"PDF resolution: {doi}")
    try:
        result = await asyncio.to_thread(unpaywall.get_paper_pdf, doi)
        if not verbose and isinstance(result, dict):
            result.pop("all_locations", None)
            result.pop("all_locations_count", None)
        return result
    except Exception as e:
        return _error_dict(f"PDF resolution failed: {str(e)}")


@mcp.tool()
async def batch_check_open_access(dois: List[str]) -> List[Dict[str, Any]]:
    """
    Check open access status for multiple papers at once. Returns whether
    each paper has a free PDF and where to find it. Runs concurrently
    for better performance.

    Args:
        dois: List of DOI strings (recommended max 50 per batch)
    """
    logger.info(f"Batch OA check: {len(dois)} DOIs")
    try:
        return await asyncio.to_thread(unpaywall.batch_check_oa, dois)
    except Exception as e:
        return _error_list(f"Batch OA check failed: {str(e)}")


# ============================================================================
# CACHE MANAGEMENT TOOLS
# ============================================================================

@mcp.tool()
async def cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics: total entries, active vs expired, size on disk,
    and breakdown by category. Useful for monitoring cache health.
    """
    logger.info("Cache stats requested")
    try:
        return await asyncio.to_thread(cache.stats)
    except Exception as e:
        return _error_dict(f"Cache stats failed: {str(e)}")


@mcp.tool()
async def cache_clear(category: Optional[str] = None) -> Dict[str, Any]:
    """
    Clear the local cache. Optionally clear only a specific category.

    Args:
        category: Category to clear (e.g., "search", "paper", "author",
                  "smart_search"). If omitted, clears everything.
    """
    logger.info(f"Cache clear: category={category}")
    try:
        count = await asyncio.to_thread(cache.clear, category)
        return {"cleared": count, "category": category or "all"}
    except Exception as e:
        return _error_dict(f"Cache clear failed: {str(e)}")


# ============================================================================

if __name__ == "__main__":
    mcp.run()
