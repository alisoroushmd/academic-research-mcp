"""
Tests for orchestrator.harvest_citations (snowball harvesting logic).

Review-level deduplication is tested in test_review_manager.py.
"""

import sys
import os
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_citation(i, doi_prefix="10.9999/cite"):
    return {
        "title": f"Citing paper {i}",
        "authors": [f"Citer {i}"],
        "year": 2024,
        "doi": f"{doi_prefix}.{i}",
        "pmid": None,
        "citationCount": 5,
    }


def _make_reference(i, doi_prefix="10.9999/ref"):
    return {
        "title": f"Referenced paper {i}",
        "authors": [f"Author {i}"],
        "year": 2020,
        "doi": f"{doi_prefix}.{i}",
        "pmid": None,
        "citationCount": 20,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_module_state(tmp_db_dir):
    """Reset db singleton before each test."""
    import db

    db._conn = None
    yield
    if db._conn is not None:
        try:
            db._conn.close()
        except Exception:
            pass
        db._conn = None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("semantic_scholar_client.get_paper_citations")
@patch("semantic_scholar_client.get_paper_references")
def test_harvest_both_directions(mock_refs, mock_cites, tmp_db_dir):
    """Both directions: 5 citations + 3 references = 8 total, all unique."""
    from orchestrator import harvest_citations

    mock_cites.return_value = [_make_citation(i) for i in range(5)]
    mock_refs.return_value = [_make_reference(i) for i in range(3)]

    result = harvest_citations(
        seed_paper_ids=["seed_id_1"],
        direction="both",
    )

    assert result["total_harvested"] == 8
    assert len(result["candidates"]) == 8
    assert result["duplicates_within_snowball"] == 0
    assert result["seed_count"] == 1


@patch("semantic_scholar_client.get_paper_citations")
@patch("semantic_scholar_client.get_paper_references")
def test_harvest_deduplicates_across_seeds(mock_refs, mock_cites, tmp_db_dir):
    """Two seeds share one citation — duplicates_within_snowball should be 1."""
    from orchestrator import harvest_citations

    shared = _make_citation(99, doi_prefix="10.9999/shared")
    seed1_citations = [shared, _make_citation(1), _make_citation(2)]
    seed2_citations = [shared, _make_citation(3)]

    mock_refs.return_value = []
    mock_cites.side_effect = [seed1_citations, seed2_citations]

    result = harvest_citations(
        seed_paper_ids=["seed_id_1", "seed_id_2"],
        direction="forward",
    )

    # 3 from seed1 + 2 from seed2 = 5 total harvested
    assert result["total_harvested"] == 5
    # After dedup within snowball: 4 unique (shared counted once)
    assert result["duplicates_within_snowball"] == 1
    assert len(result["candidates"]) == 4


@patch("semantic_scholar_client.get_paper_citations")
@patch("semantic_scholar_client.get_paper_references")
def test_harvest_deduplicates_against_review_at_server_level(
    mock_refs, mock_cites, tmp_db_dir
):
    """Verify harvest returns candidates that can be deduped against review."""
    import review_manager
    from orchestrator import harvest_citations

    review_manager._tables_initialized = False

    pre_existing = _make_citation(0, doi_prefix="10.9999/existing")

    review = review_manager.create_review("Snowball Test 3")
    search_id = review_manager.log_search(
        review["id"], "openalex", "prior search", {}, 1, 1
    )
    review_manager.add_papers(review["id"], search_id, [pre_existing], "openalex")

    # Snowball will return only that pre-existing paper
    mock_cites.return_value = [pre_existing]
    mock_refs.return_value = []

    result = harvest_citations(
        seed_paper_ids=["seed_id_1"],
        direction="both",
    )

    assert result["total_harvested"] == 1
    assert len(result["candidates"]) == 1

    # Server-level dedup: verify the candidate IS a duplicate against the review
    assert review_manager.is_duplicate(review["id"], result["candidates"][0])
