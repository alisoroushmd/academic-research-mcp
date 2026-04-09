"""
Google Scholar client using the scholarly library.

Uses the `scholarly` library for all Google Scholar interactions,
avoiding fragile HTML scraping and ToS violations.
"""

from scholarly import scholarly
from typing import Any, Dict, List, Optional


def google_scholar_search(query: str, num_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search Google Scholar using a simple keyword query.

    Parameters:
        query: The search query (e.g., paper title or topic).
        num_results: The number of results to retrieve.

    Returns:
        List of dicts with title, authors, abstract, url, year, and citations.
    """
    try:
        search_results = scholarly.search_pubs(query)
        results = []
        for _ in range(num_results):
            try:
                pub = next(search_results)
                results.append(_format_pub(pub))
            except StopIteration:
                break
        return results
    except Exception as e:
        return [{"error": f"Google Scholar search failed: {str(e)}"}]


def advanced_google_scholar_search(
    query: str,
    author: Optional[str] = None,
    year_range: Optional[tuple] = None,
    num_results: int = 5,
) -> List[Dict[str, Any]]:
    """
    Search Google Scholar using advanced filters (author, year range).

    Parameters:
        query: The search query.
        author: Author name filter.
        year_range: (start_year, end_year) filter.
        num_results: Number of results to retrieve.

    Returns:
        List of dicts with title, authors, abstract, url, year, and citations.
    """
    try:
        # Build query with author filter
        full_query = query
        if author:
            full_query = f'author:"{author}" {query}'

        search_results = scholarly.search_pubs(
            full_query,
            year_low=year_range[0] if year_range else None,
            year_high=year_range[1] if year_range else None,
        )

        results = []
        for _ in range(num_results):
            try:
                pub = next(search_results)
                results.append(_format_pub(pub))
            except StopIteration:
                break
        return results
    except Exception as e:
        return [{"error": f"Google Scholar advanced search failed: {str(e)}"}]


def _format_pub(pub) -> Dict[str, Any]:
    """Format a scholarly publication result into a clean dict."""
    bib = pub.get("bib", {})
    return {
        "title": bib.get("title", ""),
        "authors": bib.get("author", []),
        "abstract": bib.get("abstract", ""),
        "year": bib.get("pub_year", ""),
        "venue": bib.get("venue", ""),
        "citations": pub.get("num_citations", 0),
        "url": pub.get("pub_url", "") or pub.get("eprint_url", ""),
    }
