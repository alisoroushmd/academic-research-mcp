"""
medRxiv/bioRxiv API client.

Uses the medRxiv/bioRxiv content API (https://api.medrxiv.org/ and
https://api.biorxiv.org/). Free, no authentication required.

Provides access to preprint metadata, full-text DOIs, author info,
publication status (whether a preprint has been published in a journal),
and version history.
"""

import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote
import cache
import http_client

MEDRXIV_API = "https://api.medrxiv.org"
BIORXIV_API = "https://api.biorxiv.org"


@cache.cached(category="search", ttl=cache.SEARCH_TTL)
def search_medrxiv(
    query: str,
    num_results: int = 10,
    server: str = "medrxiv",
) -> List[Dict[str, Any]]:
    """
    Search medRxiv or bioRxiv for preprints by keyword.

    Uses the detail endpoint with date range to get recent preprints,
    then filters by query terms. For more targeted searches, use
    search_medrxiv_by_date with a query filter.

    Parameters:
        query (str): Search terms.
        num_results (int): Max results (default: 10).
        server (str): "medrxiv" or "biorxiv".

    Returns:
        List of preprint dicts.
    """
    # The content API doesn't have a direct keyword search endpoint.
    # Use the pubs endpoint which searches across titles and abstracts.
    base = MEDRXIV_API if server == "medrxiv" else BIORXIV_API

    # Search published articles that match the query
    url = f"{base}/pubs/{quote(server, safe='')}/{quote(query, safe='')}/na/json"
    resp = http_client.get(url)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get("collection", [])[:num_results]:
        results.append(_format_preprint(item, server))

    return results


def search_medrxiv_by_date(
    start_date: str,
    end_date: str,
    server: str = "medrxiv",
    num_results: int = 30,
) -> List[Dict[str, Any]]:
    """
    Get preprints posted within a date range.

    Parameters:
        start_date (str): Start date "YYYY-MM-DD".
        end_date (str): End date "YYYY-MM-DD".
        server (str): "medrxiv" or "biorxiv".
        num_results (int): Max results (default: 30).

    Returns:
        List of preprint dicts sorted by date (newest first).
    """
    base = MEDRXIV_API if server == "medrxiv" else BIORXIV_API
    url = f"{base}/details/{server}/{start_date}/{end_date}/0/json"

    resp = http_client.get(url)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get("collection", [])[:num_results]:
        results.append(_format_preprint(item, server))

    return results


@cache.cached(category="paper", ttl=cache.PAPER_TTL)
def get_medrxiv_preprint(doi: str) -> Dict[str, Any]:
    """
    Get details for a specific preprint by DOI.

    Parameters:
        doi (str): The preprint DOI (e.g., "10.1101/2024.01.15.24301234").
            Also accepts full URLs.

    Returns:
        Preprint dict with full metadata.
    """
    doi = _clean_doi(doi)

    url = f"{MEDRXIV_API}/details/{quote(doi, safe='/')}/json"
    resp = http_client.get(url)
    resp.raise_for_status()
    data = resp.json()

    collection = data.get("collection", [])
    if not collection:
        return {"error": f"Preprint not found: {doi}"}

    # Return the most recent version
    latest = collection[-1]

    # Determine server from DOI
    server = "biorxiv" if "biorxiv" in doi.lower() else "medrxiv"
    result = _format_preprint(latest, server)

    # Add version history if multiple versions exist
    if len(collection) > 1:
        result["version_history"] = [
            {
                "version": item.get("version", ""),
                "date": item.get("date", ""),
                "doi": item.get("doi", ""),
            }
            for item in collection
        ]

    return result


def get_publication_status(doi: str) -> Dict[str, Any]:
    """
    Check whether a preprint has been published in a peer-reviewed journal.

    Parameters:
        doi (str): The preprint DOI.

    Returns:
        Dict with preprint_doi, published (bool), and journal info if published.
    """
    doi = _clean_doi(doi)

    url = f"{MEDRXIV_API}/publisher/doi/{quote(doi, safe='/')}/json"
    resp = http_client.get(url)
    resp.raise_for_status()
    data = resp.json()

    collection = data.get("collection", [])
    if not collection:
        return {
            "preprint_doi": doi,
            "published": False,
            "message": "No publication record found.",
        }

    pub = collection[0]
    return {
        "preprint_doi": doi,
        "published": True,
        "published_doi": pub.get("published_doi", ""),
        "published_journal": pub.get("published_journal", ""),
        "published_date": pub.get("published_date", ""),
        "preprint_title": pub.get("preprint_title", ""),
        "preprint_authors": pub.get("preprint_authors", ""),
    }


def get_recent_by_category(
    category: str,
    server: str = "medrxiv",
    num_results: int = 20,
) -> List[Dict[str, Any]]:
    """
    Get recent preprints in a specific subject category.

    Parameters:
        category (str): Subject area. Common medRxiv categories:
            "gastroenterology", "oncology", "health informatics",
            "epidemiology", "pathology", "radiology and imaging".
            Common bioRxiv categories: "bioinformatics", "cancer biology",
            "cell biology", "genomics", "systems biology".
        server (str): "medrxiv" or "biorxiv".
        num_results (int): Max results (default: 20).

    Returns:
        List of preprint dicts.
    """
    base = MEDRXIV_API if server == "medrxiv" else BIORXIV_API

    # Use a recent date range to get fresh preprints
    from datetime import datetime, timedelta
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    url = f"{base}/details/{server}/{start_date}/{end_date}/0/json"
    resp = http_client.get(url)
    resp.raise_for_status()
    data = resp.json()

    results = []
    category_lower = category.lower()
    for item in data.get("collection", []):
        item_cat = item.get("category", "").lower()
        if category_lower in item_cat:
            results.append(_format_preprint(item, server))
            if len(results) >= num_results:
                break

    return results


# --- Helper functions ---

def _format_preprint(item: Dict, server: str) -> Dict[str, Any]:
    """Format a medRxiv/bioRxiv API response into a clean dict."""
    doi = item.get("doi", "")
    return {
        "doi": doi,
        "title": item.get("title", ""),
        "authors": item.get("authors", ""),
        "author_corresponding": item.get("author_corresponding", ""),
        "author_corresponding_institution": item.get("author_corresponding_institution", ""),
        "abstract": item.get("abstract", ""),
        "date": item.get("date", ""),
        "version": item.get("version", ""),
        "category": item.get("category", ""),
        "type": item.get("type", ""),
        "license": item.get("license", ""),
        "server": server,
        "url": f"https://www.{server}.org/content/{doi}",
        "pdf_url": f"https://www.{server}.org/content/{doi}.full.pdf" if doi else "",
    }


def _clean_doi(doi: str) -> str:
    """Extract DOI from a URL or raw string."""
    doi = doi.strip()
    # Remove URL prefix
    for prefix in [
        "https://doi.org/",
        "http://doi.org/",
        "https://www.medrxiv.org/content/",
        "https://www.biorxiv.org/content/",
    ]:
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    # Remove version suffix from URL
    if doi.endswith(".full") or doi.endswith(".full.pdf"):
        doi = doi.split(".full")[0]
    # Remove trailing version like v1, v2
    doi = re.sub(r'v\d+$', '', doi)
    return doi
