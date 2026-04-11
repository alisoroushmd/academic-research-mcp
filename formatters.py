"""
Output formatting and validation helpers for the MCP server.

Compact-output transformations, error helpers, and input validation
extracted from server.py to keep the tool definitions focused.
"""

import re
from typing import Any, Dict, List, Optional


# ============================================================================
# TOKEN OPTIMIZATION: Compact output mode
# ============================================================================


def compact_paper(paper: Dict[str, Any]) -> Dict[str, Any]:
    """
    Strip a paper result to essential fields for minimal token usage.
    Reduces output by ~60-70% compared to full results.
    """
    abstract = paper.get("abstract", "") or ""
    if len(abstract) > 150:
        abstract = abstract[:150].rsplit(" ", 1)[0] + "..."

    authors = paper.get("authors", [])
    if isinstance(authors, str):
        authors_short = authors[:100] + ("..." if len(authors) > 100 else "")
    elif isinstance(authors, list):
        if len(authors) > 3:
            authors_short = authors[:3] + [f"+{len(authors) - 3} more"]
        else:
            authors_short = authors
    else:
        authors_short = authors

    # Use explicit None checks to handle 0 correctly
    cited_by = paper.get("citation_count")
    if cited_by is None:
        cited_by = paper.get("cited_by_count")
    if cited_by is None:
        cited_by = paper.get("citedby")
    if cited_by is None:
        cited_by = 0

    compact = {
        "title": paper.get("title", ""),
        "authors": authors_short,
        "year": paper.get("year") or paper.get("publication_year"),
        "cited_by": cited_by,
        "doi": paper.get("doi", ""),
    }

    if abstract:
        compact["abstract_snippet"] = abstract

    oa_url = paper.get("open_access_url") or paper.get("pdf_url", "")
    if oa_url:
        compact["pdf_url"] = oa_url

    return compact


def compact_list(papers: list, brief: bool) -> list:
    """Apply compact mode to a list of papers if brief=True."""
    if not brief:
        return papers
    return [
        compact_paper(p) if isinstance(p, dict) and "error" not in p else p
        for p in papers
    ]


def compact_single(paper: dict, brief: bool) -> dict:
    """Apply compact mode to a single paper if brief=True."""
    if not brief or not isinstance(paper, dict) or "error" in paper:
        return paper
    return compact_paper(paper)


# ============================================================================
# ERROR HELPERS: Consistent error returns
# ============================================================================


def error_dict(msg: str) -> Dict[str, Any]:
    """Return a standard error dict for single-result tools."""
    return {"error": msg}


def error_list(msg: str) -> List[Dict[str, Any]]:
    """Return a standard error list for multi-result tools."""
    return [{"error": msg}]


# ============================================================================
# VALIDATION HELPERS
# ============================================================================

_ORCID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")


def validate_orcid(orcid_id: str) -> Optional[str]:
    """Validate ORCID format, return error message or None."""
    if not _ORCID_RE.match(orcid_id.strip()):
        return f"Invalid ORCID format: '{orcid_id}'. Expected DDDD-DDDD-DDDD-DDDD."
    return None


def clamp(value: int, low: int, high: int) -> int:
    """Clamp an integer to [low, high]."""
    return max(low, min(value, high))


MAX_QUERY_LENGTH = 2000


def sanitize_query(query: str) -> str:
    """Truncate oversized queries to prevent abuse and resource waste."""
    if len(query) > MAX_QUERY_LENGTH:
        return query[:MAX_QUERY_LENGTH]
    return query


def log_query(query: str, max_len: int = 80) -> str:
    """Truncate query for safe logging (avoid leaking sensitive search terms)."""
    if len(query) <= max_len:
        return query
    return query[:max_len] + "..."
