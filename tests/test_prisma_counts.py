"""
Tests for review_manager.prisma_counts()
"""

import hashlib
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _unique_title(i: int) -> str:
    """
    Return a title that is guaranteed to be distinct from any other index.

    The title_similarity threshold is 0.85; these hex-based titles share no
    meaningful words, so pairwise similarity stays well below 0.2.
    """
    h = hashlib.sha256(str(i).encode()).hexdigest()
    return f"xp{h[:24]}"


@pytest.fixture(autouse=True)
def reset_review_manager_state(tmp_db_dir):
    """Reset review_manager module-level state before each test."""
    import review_manager

    review_manager._tables_initialized = False
    review_manager._active_review_id = None
    yield
    review_manager._tables_initialized = False
    review_manager._active_review_id = None


# ---------------------------------------------------------------------------
# Test 1: empty review — all zeros
# ---------------------------------------------------------------------------


def test_prisma_counts_empty_review():
    import review_manager

    review_manager._tables_initialized = False
    review = review_manager.create_review("Empty PRISMA Review", "No searches yet")

    counts = review_manager.prisma_counts(review["id"])

    assert "error" not in counts
    assert counts["identification"]["total_records"] == 0
    assert counts["identification"]["databases"] == {}
    assert counts["identification"]["other_methods"] == {}
    assert counts["duplicates_removed"] == 0
    assert counts["unique_records"] == 0
    assert counts["screening"]["screened"] == 0
    assert counts["screening"]["screened_out"] == 0
    assert counts["screening"]["sought_for_retrieval"] == 0
    assert counts["included"] == 0


# ---------------------------------------------------------------------------
# Test 2: two searches with partial DOI overlap, plus screening pipeline
# ---------------------------------------------------------------------------


def test_prisma_counts_with_data():
    """
    Two searches:
      - pubmed:    raw=100, adds 80 papers (indices 0–79)
      - openalex:  raw=60,  adds 30 papers (indices 70–99) but indices 70–79
                   share DOIs with pubmed batch → 10 duplicates → 20 new papers

    After add_papers:
      total_raw    = 100 + 60  = 160
      unique       = 80 + 20   = 100
      duplicates   = 160 - 100 = 60

    Then:
      screen out 70 papers  → status=screened_out
      screen in  20 papers  → status=screened_in
      include    10 papers  → status=included

    Expected PRISMA:
      total_records      = 160
      duplicates_removed = 60
      unique_records     = 100
      screened           = 100
      screened_out       = 70
      sought_for_retrieval (screened_in) = 20
      included           = 10
    """
    import review_manager

    review_manager._tables_initialized = False
    review = review_manager.create_review("Full PRISMA Review", "Two-source search")

    # --- Search 1: pubmed, 80 papers added (indices 0–79) ---
    pubmed_sid = review_manager.log_search(
        review["id"], "pubmed", "gastric cancer", {}, 100, 0
    )
    pubmed_papers = [
        {
            "doi": f"10.1234/prisma.{i}",
            "title": _unique_title(i),
            "year": 2020,
            "authors": [{"name": f"Author {i}"}],
            "source": "pubmed",
        }
        for i in range(80)
    ]
    added_pubmed = review_manager.add_papers(
        review["id"], pubmed_sid, pubmed_papers, "pubmed"
    )
    assert added_pubmed == 80
    review_manager.update_search_new_count(pubmed_sid, added_pubmed)

    # --- Search 2: openalex, papers indices 70–99 (10 overlap with pubmed on DOI) ---
    openalex_sid = review_manager.log_search(
        review["id"], "openalex", "gastric cancer", {}, 60, 0
    )
    # Indices 70–79 share DOIs with pubmed batch (duplicates); 80–99 are new.
    # Titles use a different offset (i + 1000) so they are distinct from both
    # each other and from the pubmed titles, keeping similarity well below 0.85.
    openalex_papers = [
        {
            "doi": f"10.1234/prisma.{i}",
            "title": _unique_title(i + 1000),
            "year": 2021,
            "authors": [{"name": f"Coauthor {i}"}],
            "source": "openalex",
        }
        for i in range(70, 100)
    ]
    # Indices 70–79 overlap with pubmed (same DOI), indices 80–99 are new
    added_openalex = review_manager.add_papers(
        review["id"], openalex_sid, openalex_papers, "openalex"
    )
    assert added_openalex == 20  # only 80–99 are new
    review_manager.update_search_new_count(openalex_sid, added_openalex)

    # --- Retrieve all 100 unique paper IDs ---
    all_papers = review_manager.get_review_papers(review["id"], limit=200)
    assert len(all_papers) == 100
    all_ids = [p["id"] for p in all_papers]

    # --- Screen out first 70 ---
    screened_out_ids = all_ids[:70]
    review_manager.update_paper_status(review["id"], screened_out_ids, "screened_out")

    # --- Screen in next 20 ---
    screened_in_ids = all_ids[70:90]
    review_manager.update_paper_status(review["id"], screened_in_ids, "screened_in")

    # --- Include 10 of those ---
    included_ids = all_ids[90:100]
    review_manager.update_paper_status(review["id"], included_ids, "included")

    # --- Verify PRISMA counts ---
    counts = review_manager.prisma_counts(review["id"])

    assert "error" not in counts

    ident = counts["identification"]
    assert ident["total_records"] == 160
    assert "pubmed" in ident["databases"]
    assert ident["databases"]["pubmed"]["records"] == 100
    assert "openalex" in ident["databases"]
    assert ident["databases"]["openalex"]["records"] == 60
    assert ident["other_methods"] == {}

    assert counts["duplicates_removed"] == 60
    assert counts["unique_records"] == 100

    screening = counts["screening"]
    assert screening["screened"] == 100
    assert screening["screened_out"] == 70
    assert screening["sought_for_retrieval"] == 20

    assert counts["included"] == 10


# ---------------------------------------------------------------------------
# Test 3: nonexistent review ID returns error
# ---------------------------------------------------------------------------


def test_prisma_counts_not_found():
    import review_manager

    review_manager._tables_initialized = False
    # Initialize tables so the function can actually query
    review_manager.create_review("Throwaway Review")

    counts = review_manager.prisma_counts("nonexistent-review-id-xyz")

    assert "error" in counts
    assert "nonexistent-review-id-xyz" in counts["error"]


# ---------------------------------------------------------------------------
# Test 4: snowball search appears in other_methods, not databases
# ---------------------------------------------------------------------------


def test_prisma_counts_with_snowball():
    import review_manager

    review_manager._tables_initialized = False
    review = review_manager.create_review("Snowball PRISMA Review", "With snowball")

    # Regular pubmed database search
    pubmed_sid = review_manager.log_search(
        review["id"], "pubmed", "colorectal neoplasm", {}, 50, 0
    )
    pubmed_papers = [
        {
            "doi": f"10.1234/snow.pubmed.{i}",
            "title": _unique_title(i + 2000),
            "year": 2022,
            "authors": [{"name": f"Researcher {i}"}],
            "source": "pubmed",
        }
        for i in range(10)
    ]
    added_p = review_manager.add_papers(
        review["id"], pubmed_sid, pubmed_papers, "pubmed"
    )
    assert added_p == 10
    review_manager.update_search_new_count(pubmed_sid, added_p)

    # Snowball search (citation tracking)
    snowball_sid = review_manager.log_search(
        review["id"], "snowball", "citation tracking", {}, 15, 0
    )
    snowball_papers = [
        {
            "doi": f"10.1234/snow.ref.{i}",
            "title": _unique_title(i + 3000),
            "year": 2023,
            "authors": [{"name": f"Scholar {i}"}],
            "source": "snowball",
        }
        for i in range(5)
    ]
    added_s = review_manager.add_papers(
        review["id"], snowball_sid, snowball_papers, "snowball"
    )
    assert added_s == 5
    review_manager.update_search_new_count(snowball_sid, added_s)

    counts = review_manager.prisma_counts(review["id"])

    assert "error" not in counts

    ident = counts["identification"]

    # pubmed goes into databases
    assert "pubmed" in ident["databases"]
    assert ident["databases"]["pubmed"]["records"] == 50
    assert "snowball" not in ident["databases"]

    # snowball goes into other_methods
    assert "snowball" in ident["other_methods"]
    assert ident["other_methods"]["snowball"]["records"] == 15
    assert "pubmed" not in ident["other_methods"]

    # total_records sums both sources
    assert ident["total_records"] == 65

    # unique = 10 + 5 = 15 (no overlapping DOIs)
    assert counts["unique_records"] == 15
    assert counts["duplicates_removed"] == 50  # 65 - 15
