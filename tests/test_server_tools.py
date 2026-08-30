"""
Server-level tests: search_papers pagination surface and tool annotations.
"""

import asyncio
import sys
import os
from unittest.mock import MagicMock, patch


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# server.py transitively imports scholarly (Google Scholar); stub it when the
# test environment doesn't have it — nothing here exercises Google Scholar.
try:
    import scholarly  # noqa: F401
except ImportError:
    sys.modules["scholarly"] = MagicMock()

import server


_EMPTY_PAGE = {
    "total_count": 0,
    "query_translation": "",
    "papers": [],
    "offset": 0,
    "returned": 0,
    "has_more": False,
}


def test_search_papers_pubmed_returns_pagination_dict(tmp_db_dir):
    """PubMed results carry pagination metadata instead of a bare list."""
    fake_page = {
        "total_count": 500,
        "query_translation": "cancer[MeSH]",
        "papers": [{"title": "T", "doi": "10.1000/x", "authors": [], "year": 2024}],
        "offset": 200,
        "returned": 1,
        "has_more": True,
    }
    with patch("pubmed_client.search_pubmed", return_value=fake_page) as mock_search:
        result = asyncio.run(
            server.search_papers(
                query="cancer", source="pubmed", num_results=50, offset=200
            )
        )

    mock_search.assert_called_once_with("cancer", 50, 200)
    assert result["total_count"] == 500
    assert result["offset"] == 200
    assert result["returned"] == 1
    assert result["has_more"] is True
    assert isinstance(result["papers"], list)
    assert len(result["papers"]) == 1


def test_search_papers_pubmed_num_results_clamped_to_200(tmp_db_dir):
    """The old pubmed exemption (max 10000) is gone — every source caps at 200."""
    with patch("pubmed_client.search_pubmed", return_value=_EMPTY_PAGE) as mock_search:
        asyncio.run(
            server.search_papers(query="cancer", source="pubmed", num_results=10000)
        )

    assert mock_search.call_args[0][1] == 200


def test_search_papers_negative_offset_clamped_to_zero(tmp_db_dir):
    with patch("pubmed_client.search_pubmed", return_value=_EMPTY_PAGE) as mock_search:
        asyncio.run(server.search_papers(query="cancer", source="pubmed", offset=-5))

    assert mock_search.call_args[0][2] == 0


def test_delete_review_declares_destructive_hint():
    """delete_review is irreversible and must advertise destructiveHint."""
    tools = asyncio.run(server.mcp.list_tools())
    tool = next(t for t in tools if t.name == "delete_review")
    assert tool.annotations is not None
    assert tool.annotations.destructiveHint is True


def test_snowball_search_reports_actual_insert_count_after_race():
    candidates = [
        {"doi": "10.1000/one", "title": "One"},
        {"doi": "10.1000/two", "title": "Two"},
    ]
    harvest = {
        "seed_count": 1,
        "total_harvested": 2,
        "duplicates_within_snowball": 0,
        "candidates": candidates,
    }

    with (
        patch("orchestrator.async_harvest_citations", return_value=harvest),
        patch("review_manager.is_duplicate", return_value=False),
        patch("review_manager.log_search", return_value="search-id") as log_search,
        patch("review_manager.add_papers", return_value=1) as add_papers,
        patch("review_manager.update_search_new_count") as update_count,
    ):
        result = asyncio.run(
            server.snowball_search("review-id", ["seed-id"], direction="forward")
        )

    assert result["new_candidates_added"] == 1
    assert result["duplicates_against_review"] == 1
    assert log_search.call_args.kwargs["new_count"] == 0
    add_papers.assert_called_once_with("review-id", "search-id", candidates, "snowball")
    update_count.assert_called_once_with("search-id", 1)
