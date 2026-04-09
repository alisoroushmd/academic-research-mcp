"""
arXiv API client.

Uses the arXiv API (https://info.arxiv.org/help/api/index.html).
Free, no authentication required. Returns structured metadata including
abstracts, authors, categories, PDF links, and version history.

Rate limit: 1 request per 3 seconds (enforced by the client).
"""

import re
import threading
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import cache
import http_client

ARXIV_API_BASE = "http://export.arxiv.org/api/query"
ATOM_NS = "{http://www.w3.org/2005/Atom}"
OPENSEARCH_NS = "{http://a9.com/-/spec/opensearch/1.1/}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"

# Throttle to respect arXiv rate limits (thread-safe)
_last_request_time = 0
_throttle_lock = threading.Lock()


def _throttle():
    global _last_request_time
    with _throttle_lock:
        now = time.time()
        elapsed = now - _last_request_time
        if elapsed < 3.0:
            time.sleep(3.0 - elapsed)
        _last_request_time = time.time()


@cache.cached(category="search", ttl=cache.SEARCH_TTL)
def search_arxiv(
    query: str,
    num_results: int = 10,
    sort_by: str = "relevance",
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search arXiv for papers.

    Parameters:
        query (str): Search query. Supports arXiv search syntax:
            - Simple keywords: "computational pathology"
            - Author: "au:Campanella"
            - Title: "ti:foundation model endoscopy"
            - Abstract: "abs:gastric intestinal metaplasia"
            - Category: "cat:cs.CV"
            - Combine with AND, OR, ANDNOT
        num_results (int): Max results (default: 10, max: 100).
        sort_by (str): "relevance", "lastUpdatedDate", or "submittedDate".
        category (str): Filter by arXiv category (e.g., "cs.CV", "cs.AI",
            "eess.IV", "q-bio.QM"). If provided, combined with query via AND.

    Returns:
        List of paper dicts.
    """
    search_query = query
    if category:
        search_query = f"({query}) AND cat:{category}"

    sort_map = {
        "relevance": "relevance",
        "lastUpdatedDate": "lastUpdatedDate",
        "submittedDate": "submittedDate",
    }

    params = {
        "search_query": f"all:{search_query}" if " " in query and not any(
            prefix in query for prefix in ["au:", "ti:", "abs:", "cat:", "AND", "OR"]
        ) else search_query,
        "start": 0,
        "max_results": min(num_results, 100),
        "sortBy": sort_map.get(sort_by, "relevance"),
        "sortOrder": "descending",
    }

    _throttle()
    resp = http_client.get(ARXIV_API_BASE, params=params, timeout=30)
    resp.raise_for_status()

    return _parse_feed(resp.text)


@cache.cached(category="paper", ttl=cache.PAPER_TTL)
def get_arxiv_paper(arxiv_id: str) -> Dict[str, Any]:
    """
    Get details for a specific arXiv paper by ID.

    Parameters:
        arxiv_id (str): arXiv ID (e.g., "2312.00567" or "2312.00567v2").
            Also accepts full URLs like "https://arxiv.org/abs/2312.00567".

    Returns:
        Paper dict with full metadata.
    """
    # Extract ID from URL if needed
    arxiv_id = _clean_arxiv_id(arxiv_id)

    params = {
        "id_list": arxiv_id,
        "max_results": 1,
    }

    _throttle()
    resp = http_client.get(ARXIV_API_BASE, params=params, timeout=30)
    resp.raise_for_status()

    papers = _parse_feed(resp.text)
    if papers:
        return papers[0]
    return {"error": f"Paper not found: {arxiv_id}"}


def get_arxiv_by_author(
    author_name: str, num_results: int = 10, category: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get papers by a specific author.

    Parameters:
        author_name (str): Author name (e.g., "Campanella, Gabriele").
        num_results (int): Max results.
        category (str): Optional category filter.

    Returns:
        List of paper dicts sorted by submission date (newest first).
    """
    query = f'au:"{author_name}"'
    if category:
        query = f'{query} AND cat:{category}'

    params = {
        "search_query": query,
        "start": 0,
        "max_results": min(num_results, 100),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }

    _throttle()
    resp = http_client.get(ARXIV_API_BASE, params=params, timeout=30)
    resp.raise_for_status()

    return _parse_feed(resp.text)


# --- Parsing helpers ---

def _parse_feed(xml_text: str) -> List[Dict[str, Any]]:
    """Parse an arXiv Atom feed into a list of paper dicts."""
    root = ET.fromstring(xml_text)
    papers = []

    for entry in root.findall(f"{ATOM_NS}entry"):
        paper = _parse_entry(entry)
        if paper.get("title"):
            papers.append(paper)

    return papers


def _parse_entry(entry) -> Dict[str, Any]:
    """Parse a single Atom entry into a paper dict."""
    # Title (clean whitespace)
    title_el = entry.find(f"{ATOM_NS}title")
    title = _clean_text(title_el.text) if title_el is not None and title_el.text else ""

    # Abstract
    summary_el = entry.find(f"{ATOM_NS}summary")
    abstract = _clean_text(summary_el.text) if summary_el is not None and summary_el.text else ""

    # Authors
    authors = []
    for author_el in entry.findall(f"{ATOM_NS}author"):
        name_el = author_el.find(f"{ATOM_NS}name")
        if name_el is not None and name_el.text:
            authors.append(name_el.text.strip())

    # arXiv ID and URLs
    id_el = entry.find(f"{ATOM_NS}id")
    arxiv_url = id_el.text.strip() if id_el is not None and id_el.text else ""
    arxiv_id = _clean_arxiv_id(arxiv_url)

    # PDF link
    pdf_url = ""
    for link_el in entry.findall(f"{ATOM_NS}link"):
        if link_el.get("title") == "pdf":
            pdf_url = link_el.get("href", "")

    # Dates
    published_el = entry.find(f"{ATOM_NS}published")
    published = published_el.text.strip()[:10] if published_el is not None and published_el.text else ""

    updated_el = entry.find(f"{ATOM_NS}updated")
    updated = updated_el.text.strip()[:10] if updated_el is not None and updated_el.text else ""

    # Categories
    categories = []
    primary_category_el = entry.find(f"{ARXIV_NS}primary_category")
    primary_category = ""
    if primary_category_el is not None:
        primary_category = primary_category_el.get("term", "")

    for cat_el in entry.findall(f"{ATOM_NS}category"):
        term = cat_el.get("term", "")
        if term:
            categories.append(term)

    # DOI (if available)
    doi_el = entry.find(f"{ARXIV_NS}doi")
    doi = doi_el.text.strip() if doi_el is not None and doi_el.text else ""

    # Journal reference
    journal_ref_el = entry.find(f"{ARXIV_NS}journal_ref")
    journal_ref = journal_ref_el.text.strip() if journal_ref_el is not None and journal_ref_el.text else ""

    # Comment (often contains page count, conference info)
    comment_el = entry.find(f"{ARXIV_NS}comment")
    comment = comment_el.text.strip() if comment_el is not None and comment_el.text else ""

    return {
        "arxiv_id": arxiv_id,
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "published": published,
        "updated": updated,
        "primary_category": primary_category,
        "categories": categories,
        "doi": doi,
        "journal_ref": journal_ref,
        "comment": comment,
        "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}",
        "pdf_url": pdf_url or f"https://arxiv.org/pdf/{arxiv_id}",
    }


def _clean_arxiv_id(text: str) -> str:
    """Extract a clean arXiv ID from a URL or ID string."""
    text = text.strip()
    # Match patterns like 2312.00567 or 2312.00567v2
    match = re.search(r'(\d{4}\.\d{4,5}(?:v\d+)?)', text)
    if match:
        return match.group(1)
    # Older format like cs/0601001
    match = re.search(r'([a-z-]+/\d{7}(?:v\d+)?)', text)
    if match:
        return match.group(1)
    return text


def _clean_text(text: str) -> str:
    """Clean whitespace from arXiv text fields."""
    if not text:
        return ""
    return " ".join(text.split())
