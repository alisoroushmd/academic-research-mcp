"""
Tests for review_manager.py
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SAMPLE_PAPER = {
    "id": "W2741809807",
    "doi": "10.1038/nature12373",
    "title": "An integrated encyclopedia of DNA elements in the human genome",
    "year": 2012,
    "cited_by_count": 5000,
    "authors": [{"name": "ENCODE Project Consortium"}],
    "abstract": "The human genome encodes the blueprint of life.",
    "source": "Nature",
}

SAMPLE_PAPER_NO_DOI = {
    "id": "W1234567890",
    "doi": None,
    "title": "A paper without a DOI",
    "year": 2020,
    "cited_by_count": 10,
    "authors": [{"name": "Jane Doe"}],
    "abstract": "This paper has no DOI.",
    "source": "Preprint Server",
}

SAMPLE_PAPER_DUPLICATE = {
    "id": "W2741809807",
    "doi": "10.1038/nature12373",
    "title": "An integrated encyclopedia of DNA elements in the human genome",
    "year": 2012,
    "cited_by_count": 5001,
    "authors": [{"name": "ENCODE Project Consortium"}],
    "abstract": "Duplicate entry.",
    "source": "Nature",
}


@pytest.fixture(autouse=True)
def reset_review_manager_state(tmp_db_dir):
    """Reset review_manager module-level state before each test."""
    import review_manager

    review_manager._tables_initialized = False
    review_manager.set_active_review(None)
    yield
    review_manager._tables_initialized = False
    review_manager.set_active_review(None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_review():
    import review_manager

    result = review_manager.create_review("My Review", "Query about X")
    assert "id" in result
    assert result["name"] == "My Review"
    assert result["query_description"] == "Query about X"
    assert result["status"] == "active"
    assert "created_at" in result


def test_list_reviews_empty():
    import review_manager

    result = review_manager.list_reviews()
    assert result == []


def test_list_reviews_with_data():
    import review_manager

    review_manager.create_review("Review A", "First review")
    review_manager.create_review("Review B", "Second review")
    reviews = review_manager.list_reviews()
    assert len(reviews) == 2
    # Most recently updated comes first
    names = [r["name"] for r in reviews]
    assert "Review A" in names
    assert "Review B" in names
    for r in reviews:
        assert "paper_count" in r
        assert r["paper_count"] == 0


def test_get_review():
    import review_manager

    created = review_manager.create_review("Test Review", "Some description")
    result = review_manager.get_review(created["id"])
    assert result["id"] == created["id"]
    assert result["name"] == "Test Review"
    assert result["query_description"] == "Some description"
    assert result["paper_counts"]["total"] == 0
    assert result["searches"] == []


def test_get_review_not_found():
    import review_manager

    result = review_manager.get_review("nonexistent-id-000")
    assert "error" in result
    assert "nonexistent-id-000" in result["error"]


def test_add_papers_dedup_by_doi():
    import review_manager

    review = review_manager.create_review("Dedup DOI Review")
    search_id = review_manager.log_search(
        review["id"], "openalex", "test query", {}, 2, 0
    )

    # Add original paper
    added = review_manager.add_papers(
        review["id"], search_id, [SAMPLE_PAPER], "openalex"
    )
    assert added == 1

    # Add duplicate (same DOI) — should not be added
    added_dup = review_manager.add_papers(
        review["id"], search_id, [SAMPLE_PAPER_DUPLICATE], "openalex"
    )
    assert added_dup == 0

    papers = review_manager.get_review_papers(review["id"])
    assert len(papers) == 1


def test_add_papers_dedup_by_pmid():
    import review_manager

    paper_with_pmid = {
        "id": "W111",
        "doi": None,
        "pmid": "12345678",
        "title": "A paper with PMID only",
        "year": 2021,
        "authors": [{"name": "Author One"}],
        "source": "PubMed",
    }
    paper_pmid_dup = {
        "id": "W222",
        "doi": None,
        "pmid": "12345678",
        "title": "Same paper, different title variant",
        "year": 2021,
        "authors": [{"name": "Author One"}],
        "source": "PubMed",
    }

    review = review_manager.create_review("Dedup PMID Review")
    search_id = review_manager.log_search(
        review["id"], "pubmed", "pmid query", {}, 2, 0
    )

    added = review_manager.add_papers(
        review["id"], search_id, [paper_with_pmid], "pubmed"
    )
    assert added == 1

    added_dup = review_manager.add_papers(
        review["id"], search_id, [paper_pmid_dup], "pubmed"
    )
    assert added_dup == 0

    papers = review_manager.get_review_papers(review["id"])
    assert len(papers) == 1


def test_add_papers_no_doi_no_pmid():
    import review_manager

    review = review_manager.create_review("No DOI Review")
    search_id = review_manager.log_search(
        review["id"], "arxiv", "preprint query", {}, 1, 0
    )

    added = review_manager.add_papers(
        review["id"], search_id, [SAMPLE_PAPER_NO_DOI], "arxiv"
    )
    assert added == 1

    papers = review_manager.get_review_papers(review["id"])
    assert len(papers) == 1
    assert papers[0]["doi"] is None or papers[0]["doi"] == ""


def test_update_paper_status():
    import review_manager

    review = review_manager.create_review("Status Review")
    search_id = review_manager.log_search(review["id"], "openalex", "q", {}, 1, 0)
    review_manager.add_papers(review["id"], search_id, [SAMPLE_PAPER], "openalex")

    papers = review_manager.get_review_papers(review["id"])
    assert len(papers) == 1
    paper_id = papers[0]["id"]
    assert papers[0]["status"] == "new"

    updated = review_manager.update_paper_status(
        review["id"], [paper_id], "screened_in"
    )
    assert updated == 1

    papers_after = review_manager.get_review_papers(review["id"])
    assert papers_after[0]["status"] == "screened_in"

    # Invalid status should update 0 rows
    invalid_update = review_manager.update_paper_status(
        review["id"], [paper_id], "invalid_status"
    )
    assert invalid_update == 0


def test_log_search():
    import review_manager

    review = review_manager.create_review("Search Log Review")
    search_id = review_manager.log_search(
        review["id"], "openalex", "gastric cancer AI", {"year": "2020-2025"}, 42, 30
    )
    assert search_id is not None
    assert len(search_id) > 0

    detail = review_manager.get_review(review["id"])
    assert len(detail["searches"]) == 1
    s = detail["searches"][0]
    assert s["source"] == "openalex"
    assert s["query"] == "gastric cancer AI"
    assert s["result_count_raw"] == 42
    assert s["result_count_new"] == 30
    assert s["filters"] == {"year": "2020-2025"}


def test_set_active_review():
    import review_manager

    assert review_manager.get_active_review() is None

    review = review_manager.create_review("Active Review")
    result = review_manager.set_active_review(review["id"])
    assert result["active_review_id"] == review["id"]
    assert review_manager.get_active_review() == review["id"]

    # Deactivate
    result = review_manager.set_active_review(None)
    assert result["active_review_id"] is None
    assert review_manager.get_active_review() is None


def test_set_active_review_invalid_id():
    import review_manager

    result = review_manager.set_active_review("does-not-exist-xyz")
    assert "error" in result
    assert review_manager.get_active_review() is None


def test_get_review_papers_pagination():
    import review_manager

    review = review_manager.create_review("Pagination Review")
    search_id = review_manager.log_search(review["id"], "openalex", "q", {}, 5, 0)

    distinct_titles = [
        "Genomic analysis of colorectal cancer mutations",
        "Machine learning for diabetic retinopathy screening",
        "Microbiome diversity in inflammatory bowel disease",
        "Deep learning approaches to radiology image interpretation",
        "CRISPR gene editing in sickle cell disease therapy",
    ]
    papers_to_add = [
        {
            "id": f"W{i}",
            "doi": f"10.1000/pagination{i}",
            "title": distinct_titles[i],
            "year": 2020 + i,
            "authors": [{"name": f"Author {i}"}],
            "source": "openalex",
        }
        for i in range(5)
    ]
    total_added = review_manager.add_papers(
        review["id"], search_id, papers_to_add, "openalex"
    )
    assert total_added == 5

    # First page: 3 results
    page1 = review_manager.get_review_papers(review["id"], limit=3, offset=0)
    assert len(page1) == 3

    # Second page: remaining 2
    page2 = review_manager.get_review_papers(review["id"], limit=3, offset=3)
    assert len(page2) == 2

    # No overlap
    ids1 = {p["id"] for p in page1}
    ids2 = {p["id"] for p in page2}
    assert ids1.isdisjoint(ids2)

    # Status filter — all are 'new'
    new_papers = review_manager.get_review_papers(review["id"], status_filter="new")
    assert len(new_papers) == 5

    screened_papers = review_manager.get_review_papers(
        review["id"], status_filter="screened_in"
    )
    assert len(screened_papers) == 0


# ---------------------------------------------------------------------------
# DB-level dedup backstop — unique (review_id, LOWER(doi)) index + OR IGNORE
# ---------------------------------------------------------------------------


def test_unique_doi_index_blocks_raw_duplicate_inserts():
    """The unique index rejects same-review DOI duplicates even when the
    Python-side check is bypassed (e.g., a concurrent process)."""
    import json
    import sqlite3
    import time
    import uuid

    import db
    import pytest
    import review_manager

    review = review_manager.create_review("Index test", "")
    search_id = review_manager.log_search(review["id"], "openalex", "q", {}, 1, 0)
    assert (
        review_manager.add_papers(review["id"], search_id, [SAMPLE_PAPER], "openalex")
        == 1
    )

    conn = db.get_db()
    with pytest.raises(sqlite3.IntegrityError):
        # Case-different DOI: the index is on LOWER(doi), so this collides.
        conn.execute(
            """INSERT INTO review_papers
               (id, review_id, doi, pmid, title, authors, year, source, search_id, added_at, status, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?)""",
            (
                str(uuid.uuid4()),
                review["id"],
                SAMPLE_PAPER["doi"].upper(),
                "",
                "Different title, same DOI",
                json.dumps([]),
                2021,
                "s2",
                search_id,
                time.time(),
                json.dumps({}),
            ),
        )


def test_add_papers_survives_duplicate_race(monkeypatch):
    """A competing insert between preload and executemany is not counted."""
    import json
    import sqlite3
    import time
    import uuid

    import db
    import review_manager

    review = review_manager.create_review("Race test", "")
    search_id = review_manager.log_search(review["id"], "openalex", "q", {}, 1, 0)
    real_conn = db.get_db()

    class RacingConnection:
        def __init__(self, connection):
            self.connection = connection
            self.raced = False

        @property
        def total_changes(self):
            return self.connection.total_changes

        def execute(self, sql, parameters=()):
            return self.connection.execute(sql, parameters)

        def executemany(self, sql, parameters):
            if not self.raced:
                self.raced = True
                rival = sqlite3.connect(db.get_db_path())
                rival.execute(
                    """INSERT INTO review_papers
                       (id, review_id, doi, pmid, title, normalized_title,
                        authors, year, source, search_id, added_at, status, metadata)
                       VALUES (?, ?, ?, '', ?, ?, ?, ?, ?, ?, ?, 'new', ?)""",
                    (
                        str(uuid.uuid4()),
                        review["id"],
                        SAMPLE_PAPER["doi"],
                        "Racing insert",
                        "racing insert",
                        json.dumps([]),
                        2024,
                        "rival",
                        search_id,
                        time.time(),
                        json.dumps({}),
                    ),
                )
                rival.commit()
                rival.close()
            return self.connection.executemany(sql, parameters)

        def commit(self):
            return self.connection.commit()

        def rollback(self):
            return self.connection.rollback()

    racing_conn = RacingConnection(real_conn)
    monkeypatch.setattr(review_manager._db, "get_db", lambda: racing_conn)
    assert (
        review_manager.add_papers(review["id"], search_id, [SAMPLE_PAPER], "openalex")
        == 0
    )

    papers = review_manager.get_review_papers(review["id"])
    assert len(papers) == 1
    assert papers[0]["source"] == "rival"


def test_add_papers_uses_one_bulk_insert_and_one_transaction(monkeypatch):
    """A batch preloads unresolved titles and writes with one executemany."""
    import db
    import review_manager

    review = review_manager.create_review("Bulk test", "")
    search_id = review_manager.log_search(review["id"], "openalex", "q", {}, 2, 0)
    real_conn = db.get_db()

    class ConnectionProxy:
        def __init__(self, connection):
            self.connection = connection
            self.execute_sql = []
            self.executemany_calls = 0
            self.commit_calls = 0

        @property
        def total_changes(self):
            return self.connection.total_changes

        def execute(self, sql, parameters=()):
            self.execute_sql.append(" ".join(sql.split()))
            return self.connection.execute(sql, parameters)

        def executemany(self, sql, parameters):
            self.executemany_calls += 1
            return self.connection.executemany(sql, parameters)

        def commit(self):
            self.commit_calls += 1
            return self.connection.commit()

        def rollback(self):
            return self.connection.rollback()

    proxy = ConnectionProxy(real_conn)
    monkeypatch.setattr(review_manager._db, "get_db", lambda: proxy)

    papers = [
        {"doi": "10.1000/bulk-1", "title": "Bulk paper one"},
        {"pmid": "12345678", "title": "Bulk paper two"},
    ]
    assert review_manager.add_papers(review["id"], search_id, papers, "test") == 2

    unresolved_selects = [
        sql
        for sql in proxy.execute_sql
        if sql.startswith("SELECT normalized_title, title FROM review_papers")
    ]
    assert len(unresolved_selects) == 1
    assert proxy.executemany_calls == 1
    assert proxy.commit_calls == 1


def test_fuzzy_matching_only_compares_unresolved_records():
    import review_manager

    review = review_manager.create_review("Scoped fuzzy test", "")
    search_id = review_manager.log_search(review["id"], "test", "q", {}, 3, 0)

    identified = {
        "doi": "10.1000/identified",
        "title": "A distinctive clinical evidence synthesis",
    }
    unresolved_same_title = {
        "title": "A distinctive clinical evidence synthesis",
    }
    identified_similar_to_unresolved = {
        "doi": "10.1000/second",
        "title": "A distinctive clinical evidence synthesis updated",
    }

    assert review_manager.add_papers(review["id"], search_id, [identified], "test") == 1
    # Identifier-bearing records are outside the unresolved fuzzy pool.
    assert (
        review_manager.add_papers(
            review["id"], search_id, [unresolved_same_title], "test"
        )
        == 1
    )
    # DOI-bearing candidates skip fuzzy matching even when a title is similar.
    assert (
        review_manager.add_papers(
            review["id"], search_id, [identified_similar_to_unresolved], "test"
        )
        == 1
    )
    # Exact normalized unresolved title is now a duplicate.
    assert (
        review_manager.add_papers(
            review["id"],
            search_id,
            [{"title": "A DISTINCTIVE clinical-evidence synthesis!!!"}],
            "test",
        )
        == 0
    )


def test_legacy_review_schema_migrates_without_losing_records(caplog):
    """Old tables gain normalized titles and partial PMID uniqueness in place."""
    import json
    import logging
    import sqlite3
    import time

    import db
    import review_manager

    conn = db.get_db()
    conn.execute("DROP TABLE review_papers")
    conn.execute("""
        CREATE TABLE review_papers (
            id TEXT PRIMARY KEY,
            review_id TEXT NOT NULL REFERENCES reviews(id),
            doi TEXT,
            pmid TEXT,
            title TEXT NOT NULL,
            authors TEXT,
            year INTEGER,
            source TEXT NOT NULL,
            search_id TEXT REFERENCES review_searches(id),
            added_at REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            metadata TEXT
        )
    """)
    now = time.time()
    review_id = "legacy-review"
    conn.execute(
        "INSERT INTO reviews VALUES (?, ?, ?, ?, ?, ?)",
        (review_id, "Legacy", "", now, now, "active"),
    )
    legacy_rows = [
        (
            "legacy-1",
            review_id,
            "",
            "76543210",
            "Legacy: Title!",
            "[]",
            2018,
            "pubmed",
            None,
            now,
            "screened_in",
            json.dumps({"kept": 1}),
        ),
        (
            "legacy-2",
            review_id,
            "",
            "",
            "Another legacy title",
            "[]",
            2019,
            "manual",
            None,
            now,
            "included",
            json.dumps({"kept": 2}),
        ),
    ]
    conn.executemany(
        """INSERT INTO review_papers
           (id, review_id, doi, pmid, title, authors, year, source, search_id,
            added_at, status, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        legacy_rows,
    )
    conn.commit()

    review_manager._tables_initialized = False
    with caplog.at_level(logging.WARNING):
        review_manager._ensure_tables()

    migrated = conn.execute(
        "SELECT id, normalized_title, status, metadata FROM review_papers ORDER BY id"
    ).fetchall()
    assert migrated == [
        ("legacy-1", "legacy title", "screened_in", json.dumps({"kept": 1})),
        ("legacy-2", "another legacy title", "included", json.dumps({"kept": 2})),
    ]
    indexes = {row[1]: row for row in conn.execute("PRAGMA index_list(review_papers)")}
    assert indexes["idx_rp_review_pmid_unique"][2] == 1
    assert indexes["idx_rp_review_pmid_unique"][4] == 1
    assert "idx_rp_review_normalized_title" in indexes

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO review_papers
               (id, review_id, doi, pmid, title, normalized_title, authors, year,
                source, search_id, added_at, status, metadata)
               VALUES (?, ?, '', ?, ?, ?, '[]', 2020, 'test', NULL, ?, 'new', '{}')""",
            ("duplicate-pmid", review_id, "76543210", "Other", "other", now),
        )
    conn.rollback()
    assert "Could not create unique" not in caplog.text


def test_ensure_tables_warns_on_legacy_duplicate_dois(caplog):
    """A legacy DB that already holds duplicate DOIs must not crash startup —
    index creation is skipped with a warning and inserts still work."""
    import json
    import logging
    import time
    import uuid

    import db
    import review_manager

    review = review_manager.create_review("Legacy test", "")
    search_id = review_manager.log_search(review["id"], "openalex", "q", {}, 1, 0)

    conn = db.get_db()
    conn.execute("DROP INDEX idx_rp_review_doi_unique")
    for title in ("Legacy dup 1", "Legacy dup 2"):
        conn.execute(
            """INSERT INTO review_papers
               (id, review_id, doi, pmid, title, authors, year, source, search_id, added_at, status, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?)""",
            (
                str(uuid.uuid4()),
                review["id"],
                "10.1000/legacy-dup",
                "",
                title,
                json.dumps([]),
                2019,
                "openalex",
                search_id,
                time.time(),
                json.dumps({}),
            ),
        )
    conn.commit()

    review_manager._tables_initialized = False
    with caplog.at_level(logging.WARNING):
        review_manager._ensure_tables()
    assert "duplicate DOIs" in caplog.text

    # Dedup still works via the Python check alone.
    assert (
        review_manager.add_papers(
            review["id"],
            search_id,
            [{"doi": "10.1000/legacy-dup", "title": "Legacy dup 3"}],
            "openalex",
        )
        == 0
    )


# ---------------------------------------------------------------------------
# Sticky active review — startup warning support
# ---------------------------------------------------------------------------


def test_get_active_review_info():
    import review_manager

    assert review_manager.get_active_review_info() is None

    review = review_manager.create_review("Sticky review", "")
    review_manager.set_active_review(review["id"])

    info = review_manager.get_active_review_info()
    assert info is not None
    assert info["id"] == review["id"]
    assert info["name"] == "Sticky review"
    assert info["age_days"] >= 0

    review_manager.set_active_review(None)
    assert review_manager.get_active_review_info() is None
