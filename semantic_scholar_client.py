"""
Semantic Scholar Academic Graph API client.

Uses the free public API (https://api.semanticscholar.org/graph/v1/).
No API key required for basic use (100 requests/5 minutes).
Optional API key available from https://www.semanticscholar.org/product/api
for higher rate limits (1 request/second with key).

Set the environment variable S2_API_KEY to use an API key.
"""

from typing import Any, Dict, List, Optional
import http_client
import cache

S2_API_BASE = "https://api.semanticscholar.org/graph/v1"


def _headers() -> Dict[str, str]:
    """Build request headers, including API key if available."""
    h = {"Accept": "application/json"}
    key = http_client.get_env("S2_API_KEY")
    if key:
        h["x-api-key"] = key
    return h


def search_papers(
    query: str,
    num_results: int = 10,
    year: Optional[str] = None,
    fields_of_study: Optional[List[str]] = None,
    open_access_only: bool = False,
) -> List[Dict[str, Any]]:
    """
    Search for papers on Semantic Scholar.

    Parameters:
        query (str): Search query string.
        num_results (int): Number of results (max 100).
        year (str): Year filter, e.g. "2020-2025" or "2023-" or "-2020".
        fields_of_study (list): Filter by field, e.g. ["Medicine", "Computer Science"].
        open_access_only (bool): Only return open-access papers.

    Returns:
        List of paper dicts with title, authors, year, citation count, abstract,
        DOI, URL, venue, and open access info.
    """
    url = f"{S2_API_BASE}/paper/search"
    params = {
        "query": query,
        "limit": min(num_results, 100),
        "fields": "title,authors,year,citationCount,abstract,externalIds,venue,"
                  "openAccessPdf,publicationTypes,journal,influentialCitationCount",
    }
    if year:
        params["year"] = year
    if fields_of_study:
        params["fieldsOfStudy"] = ",".join(fields_of_study)
    if open_access_only:
        params["openAccessPdf"] = ""

    key = cache._cache_key("s2_search", query, num_results, year, fields_of_study, open_access_only)
    cached = cache.get(key)
    if cached is not None:
        return cached

    resp = http_client.get(url, headers=_headers(), params=params)
    resp.raise_for_status()
    data = resp.json()

    papers = [_format_paper(item) for item in data.get("data", [])]
    cache.put(key, papers, category="search", ttl=cache.SEARCH_TTL)
    return papers


def get_paper_details(paper_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific paper.

    Parameters:
        paper_id (str): Semantic Scholar paper ID, DOI (prefixed with "DOI:"),
                        PMID (prefixed with "PMID:"), ArXiv ID, or URL.

    Returns:
        Dict with full paper details including abstract, references, citations.
    """
    url = f"{S2_API_BASE}/paper/{paper_id}"
    params = {
        "fields": "title,authors,year,citationCount,abstract,externalIds,venue,"
                  "openAccessPdf,publicationTypes,journal,influentialCitationCount,"
                  "references,citations,tldr,embedding"
    }
    key = cache._cache_key("s2_paper", paper_id)
    cached = cache.get(key)
    if cached is not None:
        return cached

    resp = http_client.get(url, headers=_headers(), params=params)
    resp.raise_for_status()
    data = resp.json()

    paper = _format_paper(data)

    # Add TLDR if available
    tldr = data.get("tldr")
    if tldr:
        paper["tldr"] = tldr.get("text", "")

    # Add references (first 20)
    refs = data.get("references", []) or []
    paper["references"] = [
        {"paperId": r.get("paperId", ""), "title": r.get("title", "")}
        for r in refs[:20]
    ]

    # Add citations (first 20)
    cites = data.get("citations", []) or []
    paper["citations"] = [
        {"paperId": c.get("paperId", ""), "title": c.get("title", "")}
        for c in cites[:20]
    ]

    cache.put(key, paper, category="paper", ttl=cache.PAPER_TTL)
    return paper


def get_paper_citations(paper_id: str, num_results: int = 20) -> List[Dict[str, Any]]:
    """
    Get papers that cite a given paper.

    Parameters:
        paper_id (str): Paper ID, DOI, PMID, etc.
        num_results (int): Number of citing papers to return.

    Returns:
        List of citing paper dicts.
    """
    url = f"{S2_API_BASE}/paper/{paper_id}/citations"
    params = {
        "limit": min(num_results, 100),
        "fields": "title,authors,year,citationCount,venue,externalIds",
    }
    resp = http_client.get(url, headers=_headers(), params=params)
    resp.raise_for_status()
    data = resp.json()

    return [
        _format_paper(item.get("citingPaper", {}))
        for item in data.get("data", [])
    ]


def get_paper_references(paper_id: str, num_results: int = 20) -> List[Dict[str, Any]]:
    """
    Get papers referenced by a given paper.

    Parameters:
        paper_id (str): Paper ID, DOI, PMID, etc.
        num_results (int): Number of referenced papers to return.

    Returns:
        List of referenced paper dicts.
    """
    url = f"{S2_API_BASE}/paper/{paper_id}/references"
    params = {
        "limit": min(num_results, 100),
        "fields": "title,authors,year,citationCount,venue,externalIds",
    }
    resp = http_client.get(url, headers=_headers(), params=params)
    resp.raise_for_status()
    data = resp.json()

    return [
        _format_paper(item.get("citedPaper", {}))
        for item in data.get("data", [])
    ]


def get_author_details(author_id: str) -> Dict[str, Any]:
    """
    Get detailed author information from Semantic Scholar.

    Parameters:
        author_id (str): Semantic Scholar author ID.

    Returns:
        Dict with name, affiliations, h-index, citation count, paper count,
        and top papers.
    """
    url = f"{S2_API_BASE}/author/{author_id}"
    params = {
        "fields": "name,affiliations,homepage,paperCount,citationCount,hIndex",
    }
    resp = http_client.get(url, headers=_headers(), params=params)
    resp.raise_for_status()
    data = resp.json()

    author = {
        "author_id": data.get("authorId", ""),
        "name": data.get("name", ""),
        "affiliations": data.get("affiliations", []),
        "homepage": data.get("homepage", ""),
        "paper_count": data.get("paperCount", 0),
        "citation_count": data.get("citationCount", 0),
        "h_index": data.get("hIndex", 0),
        "s2_url": f"https://www.semanticscholar.org/author/{data.get('authorId', '')}",
    }

    return author


def search_authors(query: str, num_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search for authors on Semantic Scholar.

    Parameters:
        query (str): Author name to search.
        num_results (int): Number of results.

    Returns:
        List of author dicts with name, affiliations, paper count, citation count.
    """
    url = f"{S2_API_BASE}/author/search"
    params = {
        "query": query,
        "limit": min(num_results, 100),
        "fields": "name,affiliations,paperCount,citationCount,hIndex",
    }
    resp = http_client.get(url, headers=_headers(), params=params)
    resp.raise_for_status()
    data = resp.json()

    authors = []
    for item in data.get("data", []):
        authors.append({
            "author_id": item.get("authorId", ""),
            "name": item.get("name", ""),
            "affiliations": item.get("affiliations", []),
            "paper_count": item.get("paperCount", 0),
            "citation_count": item.get("citationCount", 0),
            "h_index": item.get("hIndex", 0),
            "s2_url": f"https://www.semanticscholar.org/author/{item.get('authorId', '')}",
        })
    return authors


def get_author_papers(
    author_id: str, num_results: int = 20
) -> List[Dict[str, Any]]:
    """
    Get papers by a specific author.

    Parameters:
        author_id (str): Semantic Scholar author ID.
        num_results (int): Number of papers to return.

    Returns:
        List of paper dicts.
    """
    url = f"{S2_API_BASE}/author/{author_id}/papers"
    params = {
        "limit": min(num_results, 100),
        "fields": "title,year,citationCount,venue,externalIds,influentialCitationCount",
    }
    resp = http_client.get(url, headers=_headers(), params=params)
    resp.raise_for_status()
    data = resp.json()

    return [_format_paper(item) for item in data.get("data", [])]


def get_recommended_papers(paper_id: str, num_results: int = 10) -> List[Dict[str, Any]]:
    """
    Get paper recommendations based on a single paper.

    Parameters:
        paper_id (str): Paper ID to base recommendations on.
        num_results (int): Number of recommendations.

    Returns:
        List of recommended paper dicts.
    """
    url = f"https://api.semanticscholar.org/recommendations/v1/papers/forpaper/{paper_id}"
    params = {
        "limit": min(num_results, 100),
        "fields": "title,authors,year,citationCount,venue,externalIds,abstract",
    }
    resp = http_client.get(url, headers=_headers(), params=params)
    resp.raise_for_status()
    data = resp.json()

    return [_format_paper(item) for item in data.get("recommendedPapers", [])]


# --- Helper ---

def _format_paper(item: Dict) -> Dict[str, Any]:
    """Format a Semantic Scholar paper response into a clean dict."""
    ext_ids = item.get("externalIds", {}) or {}
    authors = item.get("authors", []) or []
    journal = item.get("journal", {}) or {}
    oa_pdf = item.get("openAccessPdf", {}) or {}

    return {
        "paper_id": item.get("paperId", ""),
        "title": item.get("title", ""),
        "authors": [a.get("name", "") for a in authors[:10]],
        "year": item.get("year"),
        "venue": item.get("venue", "") or journal.get("name", ""),
        "citation_count": item.get("citationCount", 0),
        "influential_citation_count": item.get("influentialCitationCount", 0),
        "abstract": item.get("abstract", ""),
        "doi": ext_ids.get("DOI", ""),
        "pmid": ext_ids.get("PubMed", ""),
        "arxiv_id": ext_ids.get("ArXiv", ""),
        "publication_types": item.get("publicationTypes", []),
        "open_access_url": oa_pdf.get("url", ""),
        "s2_url": f"https://www.semanticscholar.org/paper/{item.get('paperId', '')}",
    }


def batch_get_papers(
    paper_ids: List[str],
    fields: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Get details for up to 500 papers in a single request.
    This is dramatically more efficient than individual lookups.

    Parameters:
        paper_ids: List of paper identifiers (S2 IDs, DOIs with "DOI:" prefix,
                   PMIDs with "PMID:" prefix, ArXiv IDs, or URLs). Max 500.
        fields: Comma-separated fields to return. Defaults to standard set.

    Returns:
        List of paper dicts (order matches input; None for IDs not found).
    """
    url = f"{S2_API_BASE}/paper/batch"
    if fields is None:
        fields = ("title,authors,year,citationCount,abstract,externalIds,venue,"
                  "openAccessPdf,publicationTypes,journal,influentialCitationCount")

    params = {"fields": fields}

    # Chunk into batches of 500
    results = []
    for i in range(0, len(paper_ids), 500):
        chunk = paper_ids[i:i + 500]
        resp = http_client.post(
            url,
            headers=_headers(),
            params=params,
            json={"ids": chunk},
        )
        resp.raise_for_status()
        batch = resp.json()

        for item in batch:
            if item is None:
                results.append(None)
            else:
                results.append(_format_paper(item))

    return results
