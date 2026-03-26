"""
Academic Research MCP Server

A unified MCP server providing access to seven academic research APIs
plus Unpaywall PDF resolution, local caching, and batch operations:

  1. Google Scholar — keyword search, advanced search, author profiles
  2. ORCID — researcher profiles, publications, employment, education, funding
  3. Semantic Scholar — paper search, citation graphs, author metrics, recommendations, batch lookup
  4. arXiv — CS/ML preprints, search by author/title/category, full metadata
  5. medRxiv/bioRxiv — health sciences preprints, publication status tracking
  6. OpenAlex — 250M+ works, highest throughput, no auth needed
  7. CrossRef — DOI registry fallback, 50 req/sec, comprehensive metadata
  8. Unpaywall — legal open access PDF resolution for any DOI

Features:
  - Local SQLite cache to avoid redundant API calls
  - S2 batch endpoint for up to 500 papers in one request
  - CrossRef fallback when other APIs are rate-limited

No API keys required for basic use. Optional env vars:
  - S2_API_KEY: Higher Semantic Scholar rate limits
  - OPENALEX_EMAIL: OpenAlex polite pool (10 req/sec vs 1 req/sec)
  - CROSSREF_EMAIL: CrossRef polite pool (50 req/sec)
"""

from typing import Any, Dict, List, Optional
import asyncio
import logging

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
    individual search tools — it picks the best sources, avoids redundant queries,
    and deduplicates results by DOI.

    Search priority: OpenAlex (fast, broad) → Semantic Scholar (AI/ML strength)
    → arXiv + medRxiv (preprints) → CrossRef (fallback). Stops early when
    enough unique results are found.

    Args:
        query: Search query (e.g., "gastric intestinal metaplasia deep learning")
        num_results: Target number of unique results (default: 10)
        year: Year filter (e.g., "2020-2025")
        sources: Override source order (e.g., ["arxiv", "s2"] for CS preprints).
                 Options: "openalex", "s2", "crossref", "arxiv", "medrxiv"
        include_preprints: Include arXiv/medRxiv (default: True)
        brief: Return compact results (default: True)
    """
    logging.info(f"Smart search: {query}")
    try:
        result = await asyncio.to_thread(
            orchestrator.smart_search, query, num_results, year, sources, include_preprints
        )
        if brief:
            result["results"] = _compact_list(result.get("results", []), True)
        return result
    except Exception as e:
        return {"error": f"Smart search failed: {str(e)}"}


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
    logging.info(f"Find paper: {identifier}")
    try:
        result = await asyncio.to_thread(orchestrator.find_paper, identifier)
        return _compact_single(result, brief)
    except Exception as e:
        return {"error": f"Find paper failed: {str(e)}"}


# ============================================================================
# GOOGLE SCHOLAR TOOLS
# ============================================================================

@mcp.tool()
async def google_scholar_search_keywords(query: str, num_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search Google Scholar by keywords. Returns titles, authors, abstracts, and URLs.

    Args:
        query: Search query (e.g., "gastric intestinal metaplasia deep learning")
        num_results: Number of results to return (default: 5)
    """
    logging.info(f"Google Scholar keyword search: {query}")
    try:
        return await asyncio.to_thread(google_scholar_search, query, num_results)
    except Exception as e:
        return [{"error": f"Google Scholar search failed: {str(e)}"}]


@mcp.tool()
async def google_scholar_search_advanced(
    query: str,
    author: Optional[str] = None,
    year_range: Optional[tuple] = None,
    num_results: int = 5,
) -> List[Dict[str, Any]]:
    """
    Search Google Scholar with advanced filters (author name, year range).

    Args:
        query: Search query
        author: Filter by author name (e.g., "Campanella")
        year_range: Tuple of (start_year, end_year), e.g., (2020, 2025)
        num_results: Number of results (default: 5)
    """
    logging.info(f"Google Scholar advanced search: query={query}, author={author}, years={year_range}")
    try:
        return await asyncio.to_thread(
            advanced_google_scholar_search, query, author, year_range, num_results
        )
    except Exception as e:
        return [{"error": f"Google Scholar advanced search failed: {str(e)}"}]


@mcp.tool()
async def google_scholar_author(author_name: str) -> Dict[str, Any]:
    """
    Get an author's Google Scholar profile: affiliation, interests, citation count,
    and top publications.

    Args:
        author_name: Author name (e.g., "Ali Soroush")
    """
    logging.info(f"Google Scholar author lookup: {author_name}")
    try:
        search_query = scholarly.search_author(author_name)
        author = await asyncio.to_thread(next, search_query)
        filled = await asyncio.to_thread(scholarly.fill, author)
        return {
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
        }
    except Exception as e:
        return {"error": f"Google Scholar author lookup failed: {str(e)}"}


# ============================================================================
# ORCID TOOLS
# ============================================================================

@mcp.tool()
async def orcid_search(query: str, num_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search ORCID for researchers by name or affiliation.

    Args:
        query: Search string (e.g., "Ali Soroush", "Mount Sinai gastroenterology")
        num_results: Max results (default: 5)
    """
    logging.info(f"ORCID search: {query}")
    try:
        return await asyncio.to_thread(orcid_client.search_orcid, query, num_results)
    except Exception as e:
        return [{"error": f"ORCID search failed: {str(e)}"}]


@mcp.tool()
async def orcid_profile(orcid_id: str) -> Dict[str, Any]:
    """
    Get a full ORCID profile: name, biography, keywords, employment history,
    education, and external identifiers.

    Args:
        orcid_id: ORCID iD (e.g., "0000-0002-1234-5678")
    """
    logging.info(f"ORCID profile: {orcid_id}")
    try:
        return await asyncio.to_thread(orcid_client.get_orcid_profile, orcid_id)
    except Exception as e:
        return {"error": f"ORCID profile lookup failed: {str(e)}"}


@mcp.tool()
async def orcid_works(orcid_id: str, max_works: int = 20) -> List[Dict[str, Any]]:
    """
    Get publications from an ORCID profile with DOIs, PMIDs, and journal info.

    Args:
        orcid_id: ORCID iD
        max_works: Maximum publications to return (default: 20)
    """
    logging.info(f"ORCID works: {orcid_id}")
    try:
        return await asyncio.to_thread(orcid_client.get_orcid_works, orcid_id, max_works)
    except Exception as e:
        return [{"error": f"ORCID works lookup failed: {str(e)}"}]


@mcp.tool()
async def orcid_funding(orcid_id: str) -> List[Dict[str, Any]]:
    """
    Get funding/grants from an ORCID profile: funder, title, dates, grant number.

    Args:
        orcid_id: ORCID iD
    """
    logging.info(f"ORCID funding: {orcid_id}")
    try:
        return await asyncio.to_thread(orcid_client.get_orcid_funding, orcid_id)
    except Exception as e:
        return [{"error": f"ORCID funding lookup failed: {str(e)}"}]


# ============================================================================
# SEMANTIC SCHOLAR TOOLS
# ============================================================================

@mcp.tool()
async def s2_search_papers(
    query: str,
    num_results: int = 10,
    year: Optional[str] = None,
    fields_of_study: Optional[List[str]] = None,
    open_access_only: bool = False,
    brief: bool = True,
) -> List[Dict[str, Any]]:
    """
    Search Semantic Scholar for papers. Returns titles, authors, citations,
    abstracts, DOIs, and open access links. Better than Google Scholar for
    AI/ML and computer science literature.

    Args:
        query: Search query
        num_results: Number of results (default: 10, max: 100)
        year: Year filter (e.g., "2020-2025", "2023-", "-2020")
        fields_of_study: Filter by field (e.g., ["Medicine", "Computer Science"])
        open_access_only: Only return open-access papers
        brief: Return compact results to save tokens (default: True). Set False for full metadata.
    """
    logging.info(f"S2 paper search: {query}")
    try:
        results = await asyncio.to_thread(
            s2.search_papers, query, num_results, year, fields_of_study, open_access_only
        )
        return _compact_list(results, brief)
    except Exception as e:
        return [{"error": f"Semantic Scholar search failed: {str(e)}"}]


@mcp.tool()
async def s2_paper_details(paper_id: str, brief: bool = False) -> Dict[str, Any]:
    """
    Get full details for a paper: abstract, TLDR, references, citations, and metadata.
    Accepts Semantic Scholar ID, DOI (prefix with "DOI:"), PMID (prefix with "PMID:"),
    or ArXiv ID.

    Args:
        paper_id: Paper identifier (e.g., "DOI:10.1038/s41591-023-02437-x" or "PMID:37890456")
        brief: Return compact results (default: False for detail lookups)
    """
    logging.info(f"S2 paper details: {paper_id}")
    try:
        return await asyncio.to_thread(s2.get_paper_details, paper_id)
    except Exception as e:
        return {"error": f"Semantic Scholar paper lookup failed: {str(e)}"}


@mcp.tool()
async def s2_paper_citations(paper_id: str, num_results: int = 20) -> List[Dict[str, Any]]:
    """
    Get papers that cite a given paper (forward citation graph). Useful for finding
    who built on a specific study.

    Args:
        paper_id: Paper identifier
        num_results: Number of citing papers (default: 20)
    """
    logging.info(f"S2 citations for: {paper_id}")
    try:
        return await asyncio.to_thread(s2.get_paper_citations, paper_id, num_results)
    except Exception as e:
        return [{"error": f"Semantic Scholar citations lookup failed: {str(e)}"}]


@mcp.tool()
async def s2_paper_references(paper_id: str, num_results: int = 20) -> List[Dict[str, Any]]:
    """
    Get papers referenced by a given paper (backward citation graph). Useful for
    tracing the intellectual lineage of a study.

    Args:
        paper_id: Paper identifier
        num_results: Number of referenced papers (default: 20)
    """
    logging.info(f"S2 references for: {paper_id}")
    try:
        return await asyncio.to_thread(s2.get_paper_references, paper_id, num_results)
    except Exception as e:
        return [{"error": f"Semantic Scholar references lookup failed: {str(e)}"}]


@mcp.tool()
async def s2_search_authors(query: str, num_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search for authors on Semantic Scholar. Returns name, affiliations,
    h-index, citation count, and paper count.

    Args:
        query: Author name (e.g., "Gabriele Campanella")
        num_results: Number of results (default: 5)
    """
    logging.info(f"S2 author search: {query}")
    try:
        return await asyncio.to_thread(s2.search_authors, query, num_results)
    except Exception as e:
        return [{"error": f"Semantic Scholar author search failed: {str(e)}"}]


@mcp.tool()
async def s2_author_details(author_id: str) -> Dict[str, Any]:
    """
    Get detailed Semantic Scholar author profile: h-index, citation count,
    paper count, affiliations, and homepage.

    Args:
        author_id: Semantic Scholar author ID
    """
    logging.info(f"S2 author details: {author_id}")
    try:
        return await asyncio.to_thread(s2.get_author_details, author_id)
    except Exception as e:
        return {"error": f"Semantic Scholar author lookup failed: {str(e)}"}


@mcp.tool()
async def s2_author_papers(author_id: str, num_results: int = 20) -> List[Dict[str, Any]]:
    """
    Get papers by a specific Semantic Scholar author.

    Args:
        author_id: Semantic Scholar author ID
        num_results: Number of papers (default: 20)
    """
    logging.info(f"S2 author papers: {author_id}")
    try:
        return await asyncio.to_thread(s2.get_author_papers, author_id, num_results)
    except Exception as e:
        return [{"error": f"Semantic Scholar author papers failed: {str(e)}"}]


@mcp.tool()
async def s2_recommend_papers(paper_id: str, num_results: int = 10) -> List[Dict[str, Any]]:
    """
    Get paper recommendations based on a specific paper. Useful for discovering
    related work you might have missed.

    Args:
        paper_id: Paper ID to base recommendations on
        num_results: Number of recommendations (default: 10)
    """
    logging.info(f"S2 recommendations for: {paper_id}")
    try:
        return await asyncio.to_thread(s2.get_recommended_papers, paper_id, num_results)
    except Exception as e:
        return [{"error": f"Semantic Scholar recommendations failed: {str(e)}"}]


@mcp.tool()
async def s2_batch_papers(paper_ids: List[str]) -> List[Optional[Dict[str, Any]]]:
    """
    Get details for up to 500 papers in a single request. Dramatically faster
    than individual lookups when processing reference lists, citation sets, or
    systematic review results.

    Accepts any mix of identifiers: S2 IDs, DOIs (prefix "DOI:"),
    PMIDs (prefix "PMID:"), or ArXiv IDs.

    Args:
        paper_ids: List of paper identifiers (max 500)
    """
    logging.info(f"S2 batch lookup: {len(paper_ids)} papers")
    try:
        return await asyncio.to_thread(s2.batch_get_papers, paper_ids)
    except Exception as e:
        return [{"error": f"Semantic Scholar batch lookup failed: {str(e)}"}]


# ============================================================================
# ARXIV TOOLS
# ============================================================================

@mcp.tool()
async def arxiv_search(
    query: str,
    num_results: int = 10,
    sort_by: str = "relevance",
    category: Optional[str] = None,
    brief: bool = True,
) -> List[Dict[str, Any]]:
    """
    Search arXiv for papers. Best for CS, ML, and quantitative biology preprints.
    Supports arXiv query syntax: au: (author), ti: (title), abs: (abstract),
    cat: (category), and boolean operators AND, OR, ANDNOT.

    Args:
        query: Search query (e.g., "computational pathology whole slide image",
               "au:Campanella AND ti:foundation model")
        num_results: Number of results (default: 10, max: 100)
        sort_by: "relevance", "lastUpdatedDate", or "submittedDate"
        category: Filter by arXiv category (e.g., "cs.CV", "cs.AI", "cs.LG",
                  "eess.IV", "q-bio.QM")
    """
    logging.info(f"arXiv search: {query}, category={category}")
    try:
        results = await asyncio.to_thread(
            arxiv_client.search_arxiv, query, num_results, sort_by, category
        )
        return _compact_list(results, brief)
    except Exception as e:
        return [{"error": f"arXiv search failed: {str(e)}"}]


@mcp.tool()
async def arxiv_paper(arxiv_id: str) -> Dict[str, Any]:
    """
    Get full details for a specific arXiv paper by ID or URL.

    Args:
        arxiv_id: arXiv ID (e.g., "2312.00567", "2312.00567v2") or full URL
                  (e.g., "https://arxiv.org/abs/2312.00567")
    """
    logging.info(f"arXiv paper: {arxiv_id}")
    try:
        return await asyncio.to_thread(arxiv_client.get_arxiv_paper, arxiv_id)
    except Exception as e:
        return {"error": f"arXiv paper lookup failed: {str(e)}"}


@mcp.tool()
async def arxiv_by_author(
    author_name: str,
    num_results: int = 10,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Get arXiv papers by a specific author, sorted by submission date.

    Args:
        author_name: Author name (e.g., "Campanella, Gabriele" or "Campanella")
        num_results: Number of results (default: 10)
        category: Optional category filter (e.g., "cs.CV")
    """
    logging.info(f"arXiv by author: {author_name}")
    try:
        return await asyncio.to_thread(
            arxiv_client.get_arxiv_by_author, author_name, num_results, category
        )
    except Exception as e:
        return [{"error": f"arXiv author search failed: {str(e)}"}]


# ============================================================================
# MEDRXIV / BIORXIV TOOLS
# ============================================================================

@mcp.tool()
async def medrxiv_search(
    query: str,
    num_results: int = 10,
    server: str = "medrxiv",
    brief: bool = True,
) -> List[Dict[str, Any]]:
    """
    Search medRxiv or bioRxiv for preprints.

    Args:
        query: Search terms (e.g., "gastric intestinal metaplasia AI")
        num_results: Max results (default: 10)
        server: "medrxiv" or "biorxiv"
    """
    logging.info(f"{server} search: {query}")
    try:
        results = await asyncio.to_thread(
            medrxiv_client.search_medrxiv, query, num_results, server
        )
        return _compact_list(results, brief)
    except Exception as e:
        return [{"error": f"{server} search failed: {str(e)}"}]


@mcp.tool()
async def medrxiv_by_date(
    start_date: str,
    end_date: str,
    server: str = "medrxiv",
    num_results: int = 30,
) -> List[Dict[str, Any]]:
    """
    Get preprints posted within a date range. Useful for monitoring new work.

    Args:
        start_date: Start date "YYYY-MM-DD"
        end_date: End date "YYYY-MM-DD"
        server: "medrxiv" or "biorxiv"
        num_results: Max results (default: 30)
    """
    logging.info(f"{server} by date: {start_date} to {end_date}")
    try:
        return await asyncio.to_thread(
            medrxiv_client.search_medrxiv_by_date, start_date, end_date, server, num_results
        )
    except Exception as e:
        return [{"error": f"{server} date search failed: {str(e)}"}]


@mcp.tool()
async def medrxiv_preprint(doi: str) -> Dict[str, Any]:
    """
    Get details for a specific preprint by DOI, including version history.

    Args:
        doi: Preprint DOI (e.g., "10.1101/2024.01.15.24301234") or full URL
    """
    logging.info(f"medRxiv/bioRxiv preprint: {doi}")
    try:
        return await asyncio.to_thread(medrxiv_client.get_medrxiv_preprint, doi)
    except Exception as e:
        return {"error": f"Preprint lookup failed: {str(e)}"}


@mcp.tool()
async def medrxiv_publication_status(doi: str) -> Dict[str, Any]:
    """
    Check whether a preprint has been published in a peer-reviewed journal.
    Returns the journal DOI, journal name, and publication date if published.

    Args:
        doi: Preprint DOI
    """
    logging.info(f"Publication status check: {doi}")
    try:
        return await asyncio.to_thread(medrxiv_client.get_publication_status, doi)
    except Exception as e:
        return {"error": f"Publication status check failed: {str(e)}"}


@mcp.tool()
async def medrxiv_recent_by_category(
    category: str,
    server: str = "medrxiv",
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
        num_results: Max results (default: 20)
    """
    logging.info(f"{server} recent in category: {category}")
    try:
        return await asyncio.to_thread(
            medrxiv_client.get_recent_by_category, category, server, num_results
        )
    except Exception as e:
        return [{"error": f"{server} category search failed: {str(e)}"}]


# ============================================================================
# OPENALEX TOOLS
# ============================================================================

@mcp.tool()
async def openalex_search(
    query: str,
    num_results: int = 10,
    year: Optional[str] = None,
    open_access_only: bool = False,
    sort_by: str = "relevance_score",
    brief: bool = True,
) -> List[Dict[str, Any]]:
    """
    Search OpenAlex for works. Covers 250M+ works with no rate limit concerns.
    Best choice for high-volume searches or when other APIs are throttled.

    Args:
        query: Search query
        num_results: Number of results (default: 10, max: 200)
        year: Year filter (e.g., "2023", "2020-2025", ">2022")
        open_access_only: Only return open-access works
        sort_by: "relevance_score", "cited_by_count", or "publication_date"
        brief: Return compact results to save tokens (default: True)
    """
    logging.info(f"OpenAlex search: {query}")
    try:
        results = await asyncio.to_thread(
            oalex.search_works, query, num_results, year, open_access_only, sort_by
        )
        return _compact_list(results, brief)
    except Exception as e:
        return [{"error": f"OpenAlex search failed: {str(e)}"}]


@mcp.tool()
async def openalex_work(work_id: str) -> Dict[str, Any]:
    """
    Get details for a specific work from OpenAlex. Accepts OpenAlex ID,
    DOI, or PMID.

    Args:
        work_id: OpenAlex ID (e.g., "W2741809807"), DOI (e.g., "10.1038/s41591-023-02437-x"),
                 or PMID (e.g., "pmid:37890456")
    """
    logging.info(f"OpenAlex work: {work_id}")
    try:
        return await asyncio.to_thread(oalex.get_work, work_id)
    except Exception as e:
        return {"error": f"OpenAlex work lookup failed: {str(e)}"}


@mcp.tool()
async def openalex_search_authors(query: str, num_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search for authors on OpenAlex. Returns name, affiliations, works count,
    citation count, and h-index.

    Args:
        query: Author name
        num_results: Number of results (default: 5)
    """
    logging.info(f"OpenAlex author search: {query}")
    try:
        return await asyncio.to_thread(oalex.search_authors, query, num_results)
    except Exception as e:
        return [{"error": f"OpenAlex author search failed: {str(e)}"}]


@mcp.tool()
async def openalex_author(author_id: str) -> Dict[str, Any]:
    """
    Get detailed author profile from OpenAlex: h-index, citation count,
    research topics, and ORCID.

    Args:
        author_id: OpenAlex author ID (e.g., "A5023888391") or ORCID
    """
    logging.info(f"OpenAlex author: {author_id}")
    try:
        return await asyncio.to_thread(oalex.get_author, author_id)
    except Exception as e:
        return {"error": f"OpenAlex author lookup failed: {str(e)}"}


@mcp.tool()
async def openalex_author_works(
    author_id: str,
    num_results: int = 20,
    sort_by: str = "publication_date",
) -> List[Dict[str, Any]]:
    """
    Get works by a specific author from OpenAlex.

    Args:
        author_id: OpenAlex author ID or ORCID
        num_results: Number of works (default: 20)
        sort_by: "publication_date" or "cited_by_count"
    """
    logging.info(f"OpenAlex author works: {author_id}")
    try:
        return await asyncio.to_thread(oalex.get_author_works, author_id, num_results, sort_by)
    except Exception as e:
        return [{"error": f"OpenAlex author works failed: {str(e)}"}]


@mcp.tool()
async def openalex_institution(institution_id: str) -> Dict[str, Any]:
    """
    Get institution details from OpenAlex: name, country, type, works count.

    Args:
        institution_id: OpenAlex institution ID or ROR ID
    """
    logging.info(f"OpenAlex institution: {institution_id}")
    try:
        return await asyncio.to_thread(oalex.get_institution, institution_id)
    except Exception as e:
        return {"error": f"OpenAlex institution lookup failed: {str(e)}"}


# ============================================================================
# CROSSREF TOOLS (Web Search Fallback)
# ============================================================================

@mcp.tool()
async def crossref_search(
    query: str,
    num_results: int = 10,
    year: Optional[str] = None,
    sort: str = "relevance",
    type_filter: Optional[str] = None,
    brief: bool = True,
) -> List[Dict[str, Any]]:
    """
    Search CrossRef for works. CrossRef is the DOI registry covering 150M+ works
    with very high rate limits (50 req/sec). Use as a fallback when Semantic Scholar
    or Google Scholar are rate-limited, or when you need fast, high-volume lookups.

    Args:
        query: Search query
        num_results: Number of results (default: 10, max: 100)
        year: Year or range (e.g., "2023", "2020-2025")
        sort: "relevance", "published", or "is-referenced-by-count"
        type_filter: Filter by type (e.g., "journal-article", "proceedings-article",
                     "posted-content" for preprints)
        brief: Return compact results to save tokens (default: True)
    """
    logging.info(f"CrossRef search: {query}")
    try:
        results = await asyncio.to_thread(cr.search_works, query, num_results, year, sort, type_filter)
        return _compact_list(results, brief)
    except Exception as e:
        return [{"error": f"CrossRef search failed: {str(e)}"}]


@mcp.tool()
async def crossref_doi(doi: str) -> Dict[str, Any]:
    """
    Get metadata for a work by DOI from CrossRef. The authoritative source
    for DOI metadata.

    Args:
        doi: DOI string (e.g., "10.1038/s41591-023-02437-x")
    """
    logging.info(f"CrossRef DOI lookup: {doi}")
    try:
        return await asyncio.to_thread(cr.get_work_by_doi, doi)
    except Exception as e:
        return {"error": f"CrossRef DOI lookup failed: {str(e)}"}


@mcp.tool()
async def crossref_by_author(
    author_name: str,
    query: Optional[str] = None,
    num_results: int = 20,
) -> List[Dict[str, Any]]:
    """
    Search CrossRef for works by a specific author, optionally filtered by topic.

    Args:
        author_name: Author name
        query: Optional additional search terms
        num_results: Number of results (default: 20)
    """
    logging.info(f"CrossRef author search: {author_name}")
    try:
        return await asyncio.to_thread(cr.search_by_author, author_name, query, num_results)
    except Exception as e:
        return [{"error": f"CrossRef author search failed: {str(e)}"}]




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
    logging.info(f"PDF resolution: {doi}")
    try:
        result = await asyncio.to_thread(unpaywall.get_paper_pdf, doi)
        if not verbose and isinstance(result, dict):
            result.pop("all_locations", None)
            result.pop("all_locations_count", None)
        return result
    except Exception as e:
        return {"error": f"PDF resolution failed: {str(e)}"}


@mcp.tool()
async def batch_check_open_access(dois: List[str]) -> List[Dict[str, Any]]:
    """
    Check open access status for multiple papers at once. Returns whether
    each paper has a free PDF and where to find it.

    Args:
        dois: List of DOI strings (recommended max 50 per batch)
    """
    logging.info(f"Batch OA check: {len(dois)} DOIs")
    try:
        return await asyncio.to_thread(unpaywall.batch_check_oa, dois)
    except Exception as e:
        return [{"error": f"Batch OA check failed: {str(e)}"}]


# ============================================================================
# CACHE MANAGEMENT TOOLS
# ============================================================================

@mcp.tool()
async def cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics: total entries, active vs expired, size on disk,
    and breakdown by category. Useful for monitoring cache health.
    """
    logging.info("Cache stats requested")
    try:
        return await asyncio.to_thread(cache.stats)
    except Exception as e:
        return {"error": f"Cache stats failed: {str(e)}"}


@mcp.tool()
async def cache_clear(category: Optional[str] = None) -> Dict[str, Any]:
    """
    Clear the local cache. Optionally clear only a specific category.

    Args:
        category: Category to clear (e.g., "search", "paper", "author").
                  If omitted, clears everything.
    """
    logging.info(f"Cache clear: category={category}")
    try:
        count = await asyncio.to_thread(cache.clear, category)
        return {"cleared": count, "category": category or "all"}
    except Exception as e:
        return {"error": f"Cache clear failed: {str(e)}"}


# ============================================================================

if __name__ == "__main__":
    mcp.run()
