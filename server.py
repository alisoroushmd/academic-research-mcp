"""
Academic Research MCP Server

A unified MCP server providing access to five academic research APIs:
  1. Google Scholar — keyword search, advanced search, author profiles
  2. ORCID — researcher profiles, publications, employment, education, funding
  3. Semantic Scholar — paper search, citation graphs, author metrics, recommendations
  4. arXiv — CS/ML preprints, search by author/title/category, full metadata
  5. medRxiv/bioRxiv — health sciences preprints, publication status tracking

No API keys required for basic use. Set S2_API_KEY for higher Semantic Scholar rate limits.
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

mcp = FastMCP("academic-research")


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
    """
    logging.info(f"S2 paper search: {query}")
    try:
        return await asyncio.to_thread(
            s2.search_papers, query, num_results, year, fields_of_study, open_access_only
        )
    except Exception as e:
        return [{"error": f"Semantic Scholar search failed: {str(e)}"}]


@mcp.tool()
async def s2_paper_details(paper_id: str) -> Dict[str, Any]:
    """
    Get full details for a paper: abstract, TLDR, references, citations, and metadata.
    Accepts Semantic Scholar ID, DOI (prefix with "DOI:"), PMID (prefix with "PMID:"),
    or ArXiv ID.

    Args:
        paper_id: Paper identifier (e.g., "DOI:10.1038/s41591-023-02437-x" or "PMID:37890456")
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


# ============================================================================
# ARXIV TOOLS
# ============================================================================

@mcp.tool()
async def arxiv_search(
    query: str,
    num_results: int = 10,
    sort_by: str = "relevance",
    category: Optional[str] = None,
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
        return await asyncio.to_thread(
            arxiv_client.search_arxiv, query, num_results, sort_by, category
        )
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
        return await asyncio.to_thread(
            medrxiv_client.search_medrxiv, query, num_results, server
        )
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

if __name__ == "__main__":
    mcp.run()
