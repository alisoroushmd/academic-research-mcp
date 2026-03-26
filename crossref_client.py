"""
CrossRef API client — web search fallback for academic papers.

CrossRef (https://www.crossref.org) is the authoritative DOI registry covering
150M+ works. Extremely generous rate limits (50 requests/second with polite pool),
making it the ideal fallback when other APIs are throttled.

No API key required. Set CROSSREF_EMAIL for polite pool access (faster responses).
"""

import re
from typing import Any, Dict, List, Optional
import http_client
import cache

CROSSREF_BASE = "https://api.crossref.org"


def _headers() -> Dict[str, str]:
    """Build headers with polite pool mailto if available."""
    h = {"Accept": "application/json"}
    email = http_client.get_env("CROSSREF_EMAIL", http_client.get_env("OPENALEX_EMAIL"))
    if email:
        h["User-Agent"] = f"academic-research-mcp/1.0 (mailto:{email})"
    return h


def search_works(
    query: str,
    num_results: int = 10,
    year: Optional[str] = None,
    sort: str = "relevance",
    type_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search CrossRef for works by query. This is the highest-throughput academic
    search available — use as fallback when other APIs are rate-limited.

    Parameters:
        query: Search query.
        num_results: Number of results (max 100).
        year: Year or range (e.g., "2023", "2020-2025").
        sort: Sort order — "relevance", "published", "is-referenced-by-count".
        type_filter: Filter by type (e.g., "journal-article", "proceedings-article",
                     "posted-content" for preprints).

    Returns:
        List of work dicts.
    """
    url = f"{CROSSREF_BASE}/works"
    params = {
        "query": query,
        "rows": min(num_results, 100),
        "sort": sort,
        "order": "desc" if sort != "relevance" else None,
    }

    filters = []
    if year:
        if "-" in year:
            start, end = year.split("-", 1)
            if start:
                filters.append(f"from-pub-date:{start}")
            if end:
                filters.append(f"until-pub-date:{end}")
        else:
            filters.append(f"from-pub-date:{year}")
            filters.append(f"until-pub-date:{year}")

    if type_filter:
        filters.append(f"type:{type_filter}")

    if filters:
        params["filter"] = ",".join(filters)

    # Remove None values
    params = {k: v for k, v in params.items() if v is not None}

    resp = http_client.get(url, headers=_headers(), params=params)
    resp.raise_for_status()
    data = resp.json()

    items = data.get("message", {}).get("items", [])
    return [_format_work(w) for w in items]


def get_work_by_doi(doi: str) -> Dict[str, Any]:
    """
    Get metadata for a specific work by DOI.

    Parameters:
        doi: DOI string (e.g., "10.1038/s41591-023-02437-x").

    Returns:
        Dict with work metadata.
    """
    # Clean DOI
    doi = doi.replace("https://doi.org/", "").replace("DOI:", "").strip()

    url = f"{CROSSREF_BASE}/works/{doi}"
    resp = http_client.get(url, headers=_headers())
    resp.raise_for_status()
    data = resp.json()

    return _format_work(data.get("message", {}))


def search_by_author(
    author_name: str,
    query: Optional[str] = None,
    num_results: int = 20,
) -> List[Dict[str, Any]]:
    """
    Search for works by a specific author, optionally filtered by topic.

    Parameters:
        author_name: Author name to search.
        query: Optional additional query terms.
        num_results: Number of results.

    Returns:
        List of work dicts.
    """
    url = f"{CROSSREF_BASE}/works"
    params = {
        "query.author": author_name,
        "rows": min(num_results, 100),
        "sort": "published",
        "order": "desc",
    }
    if query:
        params["query"] = query

    resp = http_client.get(url, headers=_headers(), params=params)
    resp.raise_for_status()
    data = resp.json()

    items = data.get("message", {}).get("items", [])
    return [_format_work(w) for w in items]


def get_citation_count(doi: str) -> Dict[str, Any]:
    """
    Get citation count and reference count for a DOI.

    Parameters:
        doi: DOI string.

    Returns:
        Dict with citation and reference counts.
    """
    doi = doi.replace("https://doi.org/", "").replace("DOI:", "").strip()
    url = f"{CROSSREF_BASE}/works/{doi}"
    resp = http_client.get(url, headers=_headers())
    resp.raise_for_status()
    data = resp.json().get("message", {})

    return {
        "doi": doi,
        "title": data.get("title", [""])[0] if data.get("title") else "",
        "is_referenced_by_count": data.get("is-referenced-by-count", 0),
        "references_count": data.get("references-count", 0),
    }


# --- Helper ---

def _format_work(item: Dict) -> Dict[str, Any]:
    """Format a CrossRef work response into a clean dict."""
    # Title
    titles = item.get("title", [])
    title = titles[0] if titles else ""

    # Authors
    authors = []
    for a in (item.get("author", []) or [])[:15]:
        given = a.get("given", "")
        family = a.get("family", "")
        if given and family:
            authors.append(f"{given} {family}")
        elif family:
            authors.append(family)

    # Date
    date_parts = item.get("published", {}).get("date-parts", [[]])
    if not date_parts:
        date_parts = item.get("created", {}).get("date-parts", [[]])
    parts = date_parts[0] if date_parts else []
    year = parts[0] if len(parts) > 0 else None
    pub_date = "-".join(str(p) for p in parts) if parts else ""

    # Journal
    container = item.get("container-title", [])
    venue = container[0] if container else ""

    # DOI and URLs
    doi = item.get("DOI", "")

    # License / open access
    licenses = item.get("license", [])
    is_oa = any("creativecommons" in (lic.get("URL", "") or "") for lic in licenses)

    # CrossRef abstracts are sometimes in JATS XML format — strip tags
    abstract_raw = item.get("abstract", "")
    if abstract_raw:
        abstract = re.sub(r"<[^>]+>", "", abstract_raw).strip()
    else:
        abstract = ""

    return {
        "doi": doi,
        "title": title,
        "abstract": abstract,
        "authors": authors,
        "year": year,
        "publication_date": pub_date,
        "venue": venue,
        "type": item.get("type", ""),
        "cited_by_count": item.get("is-referenced-by-count", 0),
        "references_count": item.get("references-count", 0),
        "is_open_access": is_oa,
        "issn": item.get("ISSN", []),
        "publisher": item.get("publisher", ""),
        "doi_url": f"https://doi.org/{doi}" if doi else "",
    }
