"""
Academic Research MCP Server

A unified MCP server providing access to nine academic data sources,
local caching, and systematic review management — in 25 tools.

  Data sources:
  1. OpenAlex -- 250M+ works, highest throughput, no auth needed
  2. Semantic Scholar -- citation graphs, author metrics, recommendations, batch
  3. CrossRef -- DOI registry fallback, 50 req/sec
  4. PubMed -- NCBI E-utilities, full Boolean/MeSH query syntax
  5. arXiv -- CS/ML preprints, search by author/title/category
  6. medRxiv/bioRxiv -- health sciences preprints, publication tracking
  7. Google Scholar -- keyword search, author profiles
  8. ORCID -- researcher profiles, publications, funding
  9. Unpaywall -- legal open access PDF resolution

  Systematic review tools:
  - Stateful review library with DOI/PMID/fuzzy-title deduplication
  - Snowball search (forward/backward citation harvesting via S2)
  - Auto-logged search strategies when a review is active
  - PRISMA 2020 flow diagram counts
  - Export to Zotero via DOI list (LLM bridges to Zotero MCP)

No API keys required for basic use. Optional env vars:
  - S2_API_KEY: Higher Semantic Scholar rate limits
  - OPENALEX_EMAIL: OpenAlex polite pool (10 req/sec vs 1 req/sec)
  - CROSSREF_EMAIL: CrossRef polite pool (50 req/sec)
  - NCBI_API_KEY: Higher PubMed rate limits (10 req/sec vs 3 req/sec)
"""

from typing import Any, Dict, List, Literal, Optional
import asyncio
import logging

from mcp.server.fastmcp import FastMCP

import google_scholar_client as gs
import orcid_client
import semantic_scholar_client as s2
import arxiv_client
import medrxiv_client
import openalex_client as oalex
import crossref_client as cr
import unpaywall_client as unpaywall
import orchestrator
import cache
import pubmed_client
import review_manager
from formatters import (
    compact_list as _compact_list,
    compact_single as _compact_single,
    error_dict as _error_dict,
    error_list as _error_list,
    validate_orcid as _validate_orcid,
    clamp as _clamp,
    log_query as _log_query,
    sanitize_query as _sanitize_query,
    _ORCID_RE,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

mcp = FastMCP("academic-research")


# ============================================================================
# 1. SMART SEARCH & UNIVERSAL RESOLVER (use these first)
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
    THE RECOMMENDED STARTING POINT for finding papers. Use this BEFORE find_paper.

    WORKFLOW: smart_search (discover) -> find_paper (get details by confirmed DOI).
    Do NOT guess DOIs or call find_paper with made-up identifiers. Search first,
    then use the DOIs from the results.

    Searches multiple databases with deduplication and early stopping.
    Priority: OpenAlex (fast, broad) -> Semantic Scholar -> arXiv + medRxiv
    -> CrossRef. Stops early when enough unique results are found.

    TIPS:
    - Use short, targeted queries: "Ebigbo Barrett deep learning 2019" not
      long natural-language descriptions.
    - Include author surname + key topic + year for best precision.
    - Results include DOIs — use those with find_paper for full details.

    Args:
        query: Search query — keep it focused (author + topic + year works best)
        num_results: Target number of unique results (default: 10, max: 100)
        year: Year filter (e.g., "2020-2025", "2023", ">2021")
        sources: Override source order (e.g., ["arxiv", "s2"] for CS preprints).
                 Options: "openalex", "s2", "crossref", "arxiv", "medrxiv", "pubmed"
        include_preprints: Include arXiv/medRxiv (default: True)
        brief: Return compact results (default: True)
    """
    query = _sanitize_query(query)
    num_results = _clamp(num_results, 1, 100)
    logger.info(f"Smart search: {_log_query(query)}")
    try:
        result = await asyncio.to_thread(
            orchestrator.smart_search,
            query,
            num_results,
            year,
            sources,
            include_preprints,
        )
        if brief:
            result["results"] = _compact_list(result.get("results", []), True)
        # Auto-log to active review
        active_rid = review_manager.get_active_review()
        if active_rid and result.get("results"):
            search_id = review_manager.log_search(
                active_rid,
                "smart_search",
                query,
                {"year": year, "sources_queried": result.get("sources_queried", [])},
                raw_count=result.get("total_raw", 0),
                new_count=0,
            )
            new_count = review_manager.add_papers(
                active_rid, search_id, result["results"], "smart_search"
            )
            review_manager.update_search_new_count(search_id, new_count)
            result["review_new_papers"] = new_count
        return result
    except Exception as e:
        return _error_dict(f"Smart search failed: {str(e)}")


@mcp.tool()
async def find_paper(identifier: str, brief: bool = False) -> Dict[str, Any]:
    """
    Resolve a KNOWN paper identifier to full metadata. Best with confirmed
    identifiers — use smart_search or search_papers first to discover DOIs,
    then call this with the DOI.

    IMPORTANT: Do NOT guess DOIs. If you only have an author name and topic
    description, use smart_search first (e.g., "Ebigbo Barrett deep learning
    2019") to find the DOI, then call find_paper with that DOI.

    Accepts (in order of reliability):
    - DOI: "10.1038/s41591-023-02437-x" (best — always resolves)
    - PMID: "PMID:37890456"
    - arXiv ID: "2312.00567"
    - URL: "https://arxiv.org/abs/2312.00567"
    - Exact title: "Real-time use of artificial intelligence in the evaluation
      of cancer in Barrett's oesophagus" (must be close to exact)

    Title strings work only with near-exact titles. Natural-language descriptions
    like "Ebigbo Barrett deep learning paper" will likely return the wrong paper.
    Use smart_search for those.

    Args:
        identifier: Paper identifier (DOI preferred), URL, or exact title
        brief: Return compact result (default: False for single lookups)
    """
    logger.info(f"Find paper: {_log_query(identifier)}")
    try:
        result = await asyncio.to_thread(orchestrator.find_paper, identifier)
        return _compact_single(result, brief)
    except Exception as e:
        return _error_dict(f"Find paper failed: {str(e)}")


# ============================================================================
# 2. SOURCE-SPECIFIC SEARCH
# ============================================================================


@mcp.tool()
async def search_papers(
    query: str,
    source: str = "openalex",
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
    Search a specific academic database. Use this when you need control over
    which source to query, or use smart_search for automatic multi-source search.

    For PubMed with full E-utilities syntax (MeSH terms, Boolean operators,
    field tags like [ti], [au], [mh]), use source="pubmed".

    TIPS for finding a specific paper:
    - Use short queries: "Ebigbo Barrett deep learning" not long descriptions
    - Include author surname for precision: "Hashimoto Barrett AI GIE"
    - Once you find the DOI in results, use find_paper(DOI) for full details

    Args:
        query: Search query — keep focused (3-6 key terms).
               For pubmed: supports full E-utilities syntax, e.g.
               '"intestinal metaplasia"[MeSH] AND "deep learning"[ti]'
        source: API to search. Options: "openalex" (default), "s2", "crossref",
                "arxiv", "medrxiv", "google_scholar", "pubmed".
        num_results: Number of results (default: 10, max: 200; pubmed max: 10000)
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
    query = _sanitize_query(query)
    max_for_source = 10000 if source == "pubmed" else 200
    num_results = _clamp(num_results, 1, max_for_source)
    logger.info(f"Search papers: query={_log_query(query)}, source={source}")

    try:
        if source == "openalex":
            results = await asyncio.to_thread(
                oalex.search_works,
                query,
                min(num_results, 200),
                year,
                open_access_only,
                sort_by or "relevance_score",
            )
        elif source == "s2":
            results = await asyncio.to_thread(
                s2.search_papers,
                query,
                min(num_results, 100),
                year,
                fields_of_study,
                open_access_only,
            )
        elif source == "crossref":
            results = await asyncio.to_thread(
                cr.search_works,
                query,
                min(num_results, 100),
                year,
                sort_by or "relevance",
                type_filter,
            )
        elif source == "arxiv":
            results = await asyncio.to_thread(
                arxiv_client.search_arxiv,
                query,
                min(num_results, 100),
                sort_by or "relevance",
                category,
            )
        elif source == "medrxiv":
            results = await asyncio.to_thread(
                medrxiv_client.search_medrxiv, query, num_results, server
            )
        elif source == "google_scholar":
            if author or year_range:
                results = await asyncio.to_thread(
                    gs.advanced_google_scholar_search,
                    query,
                    author,
                    year_range,
                    num_results,
                )
            else:
                results = await asyncio.to_thread(
                    gs.google_scholar_search, query, num_results
                )
        elif source == "pubmed":
            result = await asyncio.to_thread(
                pubmed_client.search_pubmed, query, num_results
            )
            results = result.get("papers", [])
        else:
            return _error_list(
                f"Unknown source: '{source}'. "
                f"Options: openalex, s2, crossref, arxiv, medrxiv, google_scholar, pubmed"
            )

        # Auto-log to active review
        active_rid = review_manager.get_active_review()
        if active_rid and results:
            search_id = review_manager.log_search(
                active_rid,
                source,
                query,
                {"year": year, "sort_by": sort_by, "type_filter": type_filter},
                raw_count=len(results),
                new_count=0,
            )
            new_count = review_manager.add_papers(
                active_rid, search_id, results, source
            )
            review_manager.update_search_new_count(search_id, new_count)

        return _compact_list(results, brief)
    except Exception as e:
        return _error_list(f"Search failed ({source}): {str(e)}")


# ============================================================================
# 3. AUTHOR TOOLS
# ============================================================================


@mcp.tool()
async def search_authors(
    query: str,
    source: str = "openalex",
    num_results: int = 5,
) -> List[Dict[str, Any]]:
    """
    Search for researchers/authors across academic databases.

    Args:
        query: Author name or affiliation (e.g., "Ali Soroush", "Mount Sinai gastroenterology")
        source: API to search. Options: "openalex" (default), "s2", "orcid",
                "google_scholar".
        num_results: Number of results (default: 5, max: 50)
    """
    num_results = _clamp(num_results, 1, 50)
    logger.info(f"Search authors: query={_log_query(query)}, source={source}")

    try:
        if source == "openalex":
            return await asyncio.to_thread(oalex.search_authors, query, num_results)
        elif source == "s2":
            return await asyncio.to_thread(s2.search_authors, query, num_results)
        elif source == "orcid":
            return await asyncio.to_thread(
                orcid_client.search_orcid, query, num_results
            )
        elif source == "google_scholar":
            try:
                result = await asyncio.to_thread(gs.search_author, query)
                return [result]
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
    logger.info(f"Get author: {_log_query(identifier)}, source={source}")

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
    logger.info(f"Get author works: {_log_query(identifier)}, source={source}")

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
                oalex.get_author_works,
                identifier,
                num_results,
                sort_by or "publication_date",
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
                arxiv_client.get_arxiv_by_author,
                identifier,
                min(num_results, 100),
                category,
            )
        else:
            return _error_list(
                f"Unknown source: '{source}'. Options: openalex, s2, orcid, crossref, arxiv"
            )
        return _compact_list(results, brief)
    except Exception as e:
        return _error_list(f"Author works lookup failed ({source}): {str(e)}")


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
# 4. CITATION NETWORK (consolidated from get_paper_citations + get_paper_references)
# ============================================================================


@mcp.tool()
async def get_paper_network(
    paper_id: str,
    direction: str = "citations",
    num_results: int = 20,
) -> List[Dict[str, Any]]:
    """
    Get the citation network around a paper. Returns papers that cite it
    (forward), papers it references (backward), or both.
    Powered by Semantic Scholar.

    Args:
        paper_id: Paper identifier (S2 ID, "DOI:...", "PMID:...", or arXiv ID)
        direction: "citations" (who cited this, default), "references" (what this cites),
                   or "both" (returns a dict with both lists)
        num_results: Number of papers per direction (default: 20, max: 100)
    """
    num_results = _clamp(num_results, 1, 100)
    logger.info(f"Paper network: {paper_id}, direction={direction}")

    try:
        if direction == "citations":
            return await asyncio.to_thread(
                s2.get_paper_citations, paper_id, num_results
            )
        elif direction == "references":
            return await asyncio.to_thread(
                s2.get_paper_references, paper_id, num_results
            )
        elif direction == "both":
            citations, references = await asyncio.gather(
                asyncio.to_thread(s2.get_paper_citations, paper_id, num_results),
                asyncio.to_thread(s2.get_paper_references, paper_id, num_results),
            )
            return {
                "citations": citations,
                "references": references,
                "citation_count": len(citations),
                "reference_count": len(references),
            }
        else:
            return _error_list(
                f"Invalid direction: '{direction}'. Options: citations, references, both"
            )
    except Exception as e:
        return _error_list(f"Paper network lookup failed: {str(e)}")


@mcp.tool()
async def recommend_papers(
    paper_id: str, num_results: int = 10
) -> List[Dict[str, Any]]:
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
    if len(paper_ids) > 500:
        return _error_list(f"Too many paper IDs: {len(paper_ids)}. Maximum is 500.")
    logger.info(f"Batch lookup: {len(paper_ids)} papers")
    try:
        return await asyncio.to_thread(s2.batch_get_papers, paper_ids)
    except Exception as e:
        return _error_list(f"Batch lookup failed: {str(e)}")


# ============================================================================
# 5. PREPRINTS (consolidated from preprints_by_date + recent_preprints + preprint_status)
# ============================================================================


@mcp.tool()
async def preprints(
    action: str = "recent",
    category: Optional[str] = None,
    doi: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    server: Literal["medrxiv", "biorxiv"] = "medrxiv",
    num_results: int = 20,
) -> Any:
    """
    Browse medRxiv/bioRxiv preprints. Three modes:

    - action="recent": Get recent preprints in a category.
      Requires: category. Example categories: "gastroenterology", "oncology",
      "health informatics", "epidemiology", "bioinformatics", "cancer biology".

    - action="date_range": Get preprints within a date range.
      Requires: start_date, end_date (YYYY-MM-DD).

    - action="status": Check if a preprint has been published in a journal.
      Requires: doi.

    Args:
        action: "recent" (default), "date_range", or "status"
        category: Subject area (for action="recent")
        doi: Preprint DOI (for action="status")
        start_date: Start date YYYY-MM-DD (for action="date_range")
        end_date: End date YYYY-MM-DD (for action="date_range")
        server: "medrxiv" or "biorxiv" (default: "medrxiv")
        num_results: Max results for recent/date_range (default: 20, max: 200)
    """
    num_results = _clamp(num_results, 1, 200)

    try:
        if action == "recent":
            if not category:
                return _error_dict("category is required for action='recent'")
            logger.info(f"{server} recent: {category}")
            return await asyncio.to_thread(
                medrxiv_client.get_recent_by_category, category, server, num_results
            )
        elif action == "date_range":
            if not start_date or not end_date:
                return _error_dict(
                    "start_date and end_date required for action='date_range'"
                )
            logger.info(f"{server} date range: {start_date} to {end_date}")
            return await asyncio.to_thread(
                medrxiv_client.search_medrxiv_by_date,
                start_date,
                end_date,
                server,
                num_results,
            )
        elif action == "status":
            if not doi:
                return _error_dict("doi is required for action='status'")
            logger.info(f"Publication status: {doi}")
            return await asyncio.to_thread(medrxiv_client.get_publication_status, doi)
        else:
            return _error_dict(
                f"Invalid action: '{action}'. Options: recent, date_range, status"
            )
    except Exception as e:
        return _error_dict(f"Preprints ({action}) failed: {str(e)}")


# ============================================================================
# 6. INSTITUTION
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
# 7. OPEN ACCESS (consolidated from find_paper_pdf + batch_check_open_access)
# ============================================================================


@mcp.tool()
async def open_access(
    dois: List[str],
    verbose: bool = False,
) -> Any:
    """
    Find legal open access PDFs for papers by DOI. Checks Unpaywall, PubMed
    Central, preprint servers, and institutional repositories.

    Pass a single DOI for full resolution details, or multiple DOIs for a
    batch status check.

    Args:
        dois: List of DOI strings (1 for full details, up to 50 for batch check).
              Examples: ["10.1038/s41591-023-02437-x"] or
              ["10.1038/s41591-023-02437-x", "10.1016/j.gie.2023.06.056"]
        verbose: [Single DOI only] Include all OA locations (default: False)
    """
    if not dois:
        return _error_dict("At least one DOI is required.")
    if len(dois) > 50:
        return _error_dict(f"Too many DOIs: {len(dois)}. Maximum is 50.")

    logger.info(f"Open access check: {len(dois)} DOIs")
    try:
        if len(dois) == 1:
            result = await asyncio.to_thread(unpaywall.get_paper_pdf, dois[0])
            if not verbose and isinstance(result, dict):
                result.pop("all_locations", None)
                result.pop("all_locations_count", None)
            return result
        else:
            return await asyncio.to_thread(unpaywall.batch_check_oa, dois)
    except Exception as e:
        return _error_dict(f"Open access check failed: {str(e)}")


# ============================================================================
# 8. CITATION VALIDATION
# ============================================================================


@mcp.tool()
async def validate_citations(
    identifiers: List[str],
) -> List[Dict[str, Any]]:
    """
    Verify that DOIs and PMIDs actually exist. Use this BEFORE presenting any
    citation to the user. Every identifier in a citation list, reference table,
    or literature review MUST be validated through this tool.

    IMPORTANT: Never present a DOI or PMID to the user without first verifying
    it through this tool or find_paper. Fabricated identifiers are a serious
    error.

    Args:
        identifiers: List of DOIs or PMIDs to validate (max 25).
                     DOIs: "10.1136/gutjnl-2019-319460"
                     PMIDs: "PMID:31375564"
    """
    if len(identifiers) > 25:
        return _error_list("Too many identifiers. Maximum is 25 per call.")

    logger.info(f"Validating {len(identifiers)} citation identifiers")

    async def _validate_one(ident: str) -> Dict[str, Any]:
        ident = ident.strip()
        entry = {"identifier": ident, "valid": False, "source": None}
        try:
            paper = await asyncio.to_thread(orchestrator.find_paper, ident)
            if isinstance(paper, dict) and "error" not in paper:
                entry["valid"] = True
                entry["source"] = paper.get("resolved_via", "unknown")
                entry["title"] = (paper.get("title", "") or "")[:100]
                entry["doi"] = paper.get("doi", "")
            else:
                entry["error"] = paper.get("error", "Not found")
                entry["action_required"] = (
                    "This identifier does not exist. Use smart_search "
                    "to find the correct paper."
                )
        except Exception as e:
            entry["error"] = str(e)
            entry["action_required"] = (
                "Validation failed. Use smart_search to find the correct DOI."
            )
        return entry

    results = await asyncio.gather(*[_validate_one(ident) for ident in identifiers])
    results = list(results)

    valid_count = sum(1 for r in results if r["valid"])
    invalid_count = len(results) - valid_count

    if invalid_count > 0:
        logger.warning(
            f"Citation validation: {invalid_count}/{len(results)} identifiers "
            f"failed verification"
        )

    return results


# ============================================================================
# 9. CACHE (consolidated from cache_stats + cache_clear)
# ============================================================================


@mcp.tool()
async def cache_manage(
    action: str = "stats",
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Manage the local API response cache.

    Args:
        action: "stats" (view cache info) or "clear" (delete entries)
        category: [clear only] Category to clear (e.g., "search", "paper",
                  "author", "smart_search"). If omitted, clears everything.
    """
    logger.info(f"Cache {action}: category={category}")
    try:
        if action == "stats":
            return await asyncio.to_thread(cache.stats)
        elif action == "clear":
            count = await asyncio.to_thread(cache.clear, category)
            return {"cleared": count, "category": category or "all"}
        else:
            return _error_dict(f"Invalid action: '{action}'. Options: stats, clear")
    except Exception as e:
        return _error_dict(f"Cache {action} failed: {str(e)}")


# ============================================================================
# 10. SYSTEMATIC REVIEW TOOLS
# ============================================================================


@mcp.tool()
async def create_review(name: str, query_description: str = "") -> Dict[str, Any]:
    """
    Create a new systematic review. This is the first step in a PRISMA-compliant
    review workflow. After creating, use set_active_review to enable auto-logging.

    Args:
        name: Short name for the review (e.g., "GIM risk stratification SR")
        query_description: The research question or PICO statement
    """
    logger.info(f"Create review: {name}")
    try:
        return await asyncio.to_thread(
            review_manager.create_review, name, query_description
        )
    except Exception as e:
        return _error_dict(f"Create review failed: {str(e)}")


@mcp.tool()
async def reviews(review_id: Optional[str] = None) -> Any:
    """
    List all reviews (no args) or get full details for a specific review.

    Args:
        review_id: If provided, returns full details (search log, paper counts
                   by status). If omitted, lists all reviews with paper counts.
    """
    try:
        if review_id:
            return await asyncio.to_thread(review_manager.get_review, review_id)
        else:
            return await asyncio.to_thread(review_manager.list_reviews)
    except Exception as e:
        return _error_dict(f"Reviews failed: {str(e)}")


@mcp.tool()
async def delete_review(review_id: str) -> Dict[str, Any]:
    """
    Delete a review and all its associated papers and searches.
    This is irreversible.

    Args:
        review_id: Review UUID to delete
    """
    logger.info(f"Delete review: {review_id}")
    try:
        return await asyncio.to_thread(review_manager.delete_review, review_id)
    except Exception as e:
        return _error_dict(f"Delete review failed: {str(e)}")


@mcp.tool()
async def set_active_review(review_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Set the active review for auto-logging. When active, all searches
    (smart_search, search_papers) automatically log results and deduplicate
    against this review's paper library.

    Pass null/None to deactivate.

    Args:
        review_id: Review UUID to activate, or null to deactivate
    """
    logger.info(f"Set active review: {review_id}")
    return review_manager.set_active_review(review_id)


@mcp.tool()
async def update_paper_status(
    review_id: str,
    paper_ids: List[str],
    status: str,
) -> Dict[str, Any]:
    """
    Batch update screening status for papers in a review.

    Args:
        review_id: Review UUID
        paper_ids: List of paper UUIDs to update
        status: New status — "new", "screened_in", "screened_out", or "included"
    """
    valid = {"new", "screened_in", "screened_out", "included"}
    if status not in valid:
        return _error_dict(
            f"Invalid status: '{status}'. Options: {', '.join(sorted(valid))}"
        )
    logger.info(f"Update {len(paper_ids)} papers to '{status}' in review {review_id}")
    try:
        count = await asyncio.to_thread(
            review_manager.update_paper_status, review_id, paper_ids, status
        )
        return {"updated": count, "status": status}
    except Exception as e:
        return _error_dict(f"Update paper status failed: {str(e)}")


@mcp.tool()
async def get_review_papers(
    review_id: str,
    status_filter: Optional[str] = None,
    search_id: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Get paginated papers from a review, optionally filtered by status or search.

    Args:
        review_id: Review UUID
        status_filter: Filter by status ("new", "screened_in", "screened_out", "included")
        search_id: Filter by search UUID (e.g., to see snowball results)
        offset: Pagination offset (default: 0)
        limit: Page size (default: 50, max: 200)
    """
    limit = _clamp(limit, 1, 200)
    try:
        return await asyncio.to_thread(
            review_manager.get_review_papers,
            review_id,
            status_filter,
            search_id,
            offset,
            limit,
        )
    except Exception as e:
        return _error_list(f"Get review papers failed: {str(e)}")


@mcp.tool()
async def add_papers_to_review(
    review_id: str,
    identifiers: List[str],
) -> Dict[str, Any]:
    """
    Manually add papers to a review by DOI or PMID. Use this for papers
    found through reading, reference lists, or expert recommendation that
    weren't captured by search tools.

    Each identifier is resolved via find_paper, then deduplicated against
    the review library before adding.

    Args:
        review_id: Review UUID
        identifiers: List of DOIs or PMIDs (max 50)
    """
    if len(identifiers) > 50:
        return _error_dict("Maximum 50 identifiers per call.")

    logger.info(f"Manual add to review {review_id}: {len(identifiers)} papers")

    try:

        async def _resolve(ident: str):
            return await asyncio.to_thread(orchestrator.find_paper, ident.strip())

        resolved = await asyncio.gather(*[_resolve(i) for i in identifiers])

        papers = []
        errors = []
        for ident, result in zip(identifiers, resolved):
            if isinstance(result, dict) and "error" not in result:
                papers.append(result)
            else:
                errors.append(
                    {
                        "identifier": ident,
                        "error": result.get("error", "Not found")
                        if isinstance(result, dict)
                        else "Not found",
                    }
                )

        search_id = review_manager.log_search(
            review_id,
            source="manual",
            query=f"Manual addition of {len(identifiers)} papers",
            filters={"identifiers": identifiers},
            raw_count=len(papers),
            new_count=0,
        )
        new_count = review_manager.add_papers(review_id, search_id, papers, "manual")
        review_manager.update_search_new_count(search_id, new_count)

        return {
            "resolved": len(papers),
            "new_added": new_count,
            "duplicates_skipped": len(papers) - new_count,
            "errors": errors,
            "search_id": search_id,
        }
    except Exception as e:
        return _error_dict(f"Add papers to review failed: {str(e)}")


@mcp.tool()
async def snowball_search(
    review_id: str,
    seed_paper_ids: List[str],
    direction: str = "both",
) -> Dict[str, Any]:
    """
    Harvest citations and/or references from seed papers, deduplicate against
    the review library, and add new candidates.

    Args:
        review_id: Review UUID to add candidates to
        seed_paper_ids: List of DOIs or S2 paper IDs (max 50)
        direction: "forward" (who cited these), "backward" (what these cite), or "both"
    """
    if len(seed_paper_ids) > 50:
        return _error_dict("Maximum 50 seed papers per snowball search.")
    if direction not in ("forward", "backward", "both"):
        return _error_dict(
            f"Invalid direction: '{direction}'. Options: forward, backward, both"
        )
    logger.info(f"Snowball search: {len(seed_paper_ids)} seeds, direction={direction}")
    try:
        import json as _json

        harvest = await orchestrator.async_harvest_citations(seed_paper_ids, direction)
        if "error" in harvest:
            return harvest

        candidates = harvest["candidates"]

        new_papers = []
        duplicates_against_review = 0
        for paper in candidates:
            if review_manager.is_duplicate(review_id, paper):
                duplicates_against_review += 1
            else:
                new_papers.append(paper)

        search_id = review_manager.log_search(
            review_id,
            source="snowball",
            query=_json.dumps(seed_paper_ids),
            filters={"direction": direction},
            raw_count=harvest["total_harvested"],
            new_count=len(new_papers),
        )
        if new_papers:
            review_manager.add_papers(review_id, search_id, new_papers, "snowball")

        return {
            "seed_count": harvest["seed_count"],
            "total_harvested": harvest["total_harvested"],
            "duplicates_within_snowball": harvest["duplicates_within_snowball"],
            "duplicates_against_review": duplicates_against_review,
            "new_candidates_added": len(new_papers),
            "search_id": search_id,
        }
    except Exception as e:
        return _error_dict(f"Snowball search failed: {str(e)}")


@mcp.tool()
async def export_review(
    review_id: str,
    status_filter: str = "all",
    format: str = "dois",
) -> Dict[str, Any]:
    """
    Export papers from a review for Zotero import or other tools.

    Args:
        review_id: Review UUID
        status_filter: "all", "new", "screened_in", "screened_out", or "included"
        format: "dois" (list of DOI strings) or "full" (full paper dicts)
    """
    logger.info(f"Export review {review_id}: filter={status_filter}, format={format}")
    try:
        sf = None if status_filter == "all" else status_filter
        papers = await asyncio.to_thread(
            review_manager.get_review_papers, review_id, sf, None, 0, 10000
        )
        if format == "dois":
            dois = [p["doi"] for p in papers if p.get("doi")]
            return {"review_id": review_id, "count": len(dois), "dois": dois}
        else:
            return {"review_id": review_id, "count": len(papers), "papers": papers}
    except Exception as e:
        return _error_dict(f"Export review failed: {str(e)}")


@mcp.tool()
async def prisma_counts(review_id: str) -> Dict[str, Any]:
    """
    Get PRISMA 2020 flow diagram counts for a review.

    Args:
        review_id: Review UUID
    """
    logger.info(f"PRISMA counts for review {review_id}")
    try:
        return await asyncio.to_thread(review_manager.prisma_counts, review_id)
    except Exception as e:
        return _error_dict(f"PRISMA counts failed: {str(e)}")


# ============================================================================

if __name__ == "__main__":
    import os

    if not os.environ.get("OPENALEX_EMAIL"):
        logger.warning(
            "OPENALEX_EMAIL not set. Unpaywall PDF resolution will be unavailable "
            "and OpenAlex/CrossRef will use lower rate limits."
        )

    # Clean up expired cache entries on startup
    cache.cleanup()
    mcp.run()
