# review_manager.py
"""
Systematic review library state manager.

Manages reviews, paper deduplication, search logging, and PRISMA counts
in the shared SQLite database.
"""

import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

import db as _db
from utils import title_similarity

logger = logging.getLogger(__name__)

_tables_initialized = False
_lock = _db._lock


def _ensure_tables():
    """Create review tables if they don't exist."""
    global _tables_initialized
    if _tables_initialized:
        return
    conn = _db.get_db()
    with _lock:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                query_description TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'active'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS review_searches (
                id TEXT PRIMARY KEY,
                review_id TEXT NOT NULL REFERENCES reviews(id),
                source TEXT NOT NULL,
                query TEXT NOT NULL,
                filters TEXT,
                executed_at REAL NOT NULL,
                result_count_raw INTEGER NOT NULL,
                result_count_new INTEGER NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_review_searches_review ON review_searches(review_id)"
        )
        conn.execute("""
            CREATE TABLE IF NOT EXISTS review_papers (
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
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rp_review ON review_papers(review_id)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rp_doi ON review_papers(doi)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rp_pmid ON review_papers(pmid)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rp_status ON review_papers(review_id, status)"
        )
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()
    _tables_initialized = True


def create_review(name: str, query_description: str = "") -> Dict[str, Any]:
    _ensure_tables()
    review_id = str(uuid.uuid4())
    now = time.time()
    conn = _db.get_db()
    with _lock:
        conn.execute(
            "INSERT INTO reviews (id, name, query_description, created_at, updated_at, status) VALUES (?, ?, ?, ?, ?, ?)",
            (review_id, name, query_description, now, now, "active"),
        )
        conn.commit()
    return {
        "id": review_id,
        "name": name,
        "query_description": query_description,
        "status": "active",
        "created_at": now,
    }


def list_reviews() -> List[Dict[str, Any]]:
    _ensure_tables()
    conn = _db.get_db()
    with _lock:
        rows = conn.execute(
            """SELECT r.id, r.name, r.query_description, r.status, r.created_at, r.updated_at,
                      (SELECT COUNT(*) FROM review_papers WHERE review_id = r.id) as paper_count
               FROM reviews r ORDER BY r.updated_at DESC"""
        ).fetchall()
    return [
        {
            "id": r[0],
            "name": r[1],
            "query_description": r[2],
            "status": r[3],
            "created_at": r[4],
            "updated_at": r[5],
            "paper_count": r[6],
        }
        for r in rows
    ]


def delete_review(review_id: str) -> Dict[str, Any]:
    """Delete a review and all its associated papers and searches."""
    _ensure_tables()
    conn = _db.get_db()
    with _lock:
        row = conn.execute(
            "SELECT id, name FROM reviews WHERE id = ?", (review_id,)
        ).fetchone()
    if row is None:
        return {"error": f"Review not found: {review_id}"}

    name = row[1]
    with _lock:
        conn.execute("DELETE FROM review_papers WHERE review_id = ?", (review_id,))
        conn.execute("DELETE FROM review_searches WHERE review_id = ?", (review_id,))
        conn.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
        # Clear active review if this was the active one
        active = conn.execute(
            "SELECT value FROM settings WHERE key = 'active_review_id'"
        ).fetchone()
        if active and active[0] == review_id:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('active_review_id', NULL)"
            )
        conn.commit()
    return {"deleted": review_id, "name": name}


def get_review(review_id: str) -> Dict[str, Any]:
    _ensure_tables()
    conn = _db.get_db()
    with _lock:
        row = conn.execute(
            "SELECT id, name, query_description, status, created_at, updated_at FROM reviews WHERE id = ?",
            (review_id,),
        ).fetchone()
    if row is None:
        return {"error": f"Review not found: {review_id}"}

    with _lock:
        status_rows = conn.execute(
            "SELECT status, COUNT(*) FROM review_papers WHERE review_id = ? GROUP BY status",
            (review_id,),
        ).fetchall()
        total_papers = conn.execute(
            "SELECT COUNT(*) FROM review_papers WHERE review_id = ?",
            (review_id,),
        ).fetchone()[0]
        search_rows = conn.execute(
            """SELECT id, source, query, filters, executed_at, result_count_raw, result_count_new
               FROM review_searches WHERE review_id = ? ORDER BY executed_at""",
            (review_id,),
        ).fetchall()

    paper_counts = {"total": total_papers}
    for s, c in status_rows:
        paper_counts[s] = c

    searches = [
        {
            "id": s[0],
            "source": s[1],
            "query": s[2],
            "filters": json.loads(s[3]) if s[3] else {},
            "executed_at": s[4],
            "result_count_raw": s[5],
            "result_count_new": s[6],
        }
        for s in search_rows
    ]

    return {
        "id": row[0],
        "name": row[1],
        "query_description": row[2],
        "status": row[3],
        "created_at": row[4],
        "updated_at": row[5],
        "paper_counts": paper_counts,
        "searches": searches,
    }


def add_papers(
    review_id: str, search_id: str, papers: List[Dict[str, Any]], source: str
) -> int:
    _ensure_tables()
    new_count = 0
    conn = _db.get_db()
    now = time.time()

    for paper in papers:
        if is_duplicate(review_id, paper):
            continue
        paper_id = str(uuid.uuid4())
        doi = _extract_doi(paper)
        pmid = paper.get("pmid") or ""
        title = paper.get("title", "") or ""
        authors = json.dumps(paper.get("authors", []))
        year = paper.get("year")
        metadata = json.dumps(paper)

        with _lock:
            conn.execute(
                """INSERT INTO review_papers
                   (id, review_id, doi, pmid, title, authors, year, source, search_id, added_at, status, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?)""",
                (
                    paper_id,
                    review_id,
                    doi,
                    pmid,
                    title,
                    authors,
                    year,
                    source,
                    search_id,
                    now,
                    metadata,
                ),
            )
        new_count += 1

    with _lock:
        conn.commit()
        conn.execute("UPDATE reviews SET updated_at = ? WHERE id = ?", (now, review_id))
        conn.commit()
    return new_count


def is_duplicate(review_id: str, paper: Dict[str, Any]) -> bool:
    conn = _db.get_db()

    doi = _extract_doi(paper)
    if doi:
        with _lock:
            row = conn.execute(
                "SELECT 1 FROM review_papers WHERE review_id = ? AND LOWER(doi) = ?",
                (review_id, doi.lower()),
            ).fetchone()
        if row:
            return True
        # DOI uniquely identifies a paper. If DOI didn't match, the paper is
        # new — skip the expensive O(n) title similarity scan.
        return False

    pmid = paper.get("pmid") or ""
    if pmid:
        with _lock:
            row = conn.execute(
                "SELECT 1 FROM review_papers WHERE review_id = ? AND pmid = ?",
                (review_id, pmid),
            ).fetchone()
        if row:
            return True
        # PMID also uniquely identifies — skip title scan.
        return False

    # No DOI or PMID: fall back to fuzzy title matching
    title = paper.get("title", "") or ""
    if title:
        with _lock:
            existing_titles = conn.execute(
                "SELECT title FROM review_papers WHERE review_id = ?",
                (review_id,),
            ).fetchall()

        for (existing_title,) in existing_titles:
            if title_similarity(title, existing_title) >= 0.85:
                return True

    return False


def log_search(
    review_id: str,
    source: str,
    query: str,
    filters: Dict[str, Any],
    raw_count: int,
    new_count: int,
) -> str:
    _ensure_tables()
    search_id = str(uuid.uuid4())
    conn = _db.get_db()
    with _lock:
        conn.execute(
            """INSERT INTO review_searches
               (id, review_id, source, query, filters, executed_at, result_count_raw, result_count_new)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                search_id,
                review_id,
                source,
                query,
                json.dumps(filters),
                time.time(),
                raw_count,
                new_count,
            ),
        )
        conn.commit()
    return search_id


def update_paper_status(review_id: str, paper_ids: List[str], status: str) -> int:
    _ensure_tables()
    valid_statuses = {"new", "screened_in", "screened_out", "included"}
    if status not in valid_statuses:
        return 0
    conn = _db.get_db()
    placeholders = ",".join("?" * len(paper_ids))
    with _lock:
        cursor = conn.execute(
            f"UPDATE review_papers SET status = ? WHERE review_id = ? AND id IN ({placeholders})",
            [status, review_id] + paper_ids,
        )
        conn.commit()
    return cursor.rowcount


def get_review_papers(
    review_id: str,
    status_filter: Optional[str] = None,
    search_id: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    _ensure_tables()
    conn = _db.get_db()
    query = "SELECT id, doi, pmid, title, authors, year, source, search_id, added_at, status FROM review_papers WHERE review_id = ?"
    params: list = [review_id]

    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)
    if search_id:
        query += " AND search_id = ?"
        params.append(search_id)

    query += " ORDER BY added_at LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with _lock:
        rows = conn.execute(query, params).fetchall()

    return [
        {
            "id": r[0],
            "doi": r[1],
            "pmid": r[2],
            "title": r[3],
            "authors": json.loads(r[4]) if r[4] else [],
            "year": r[5],
            "source": r[6],
            "search_id": r[7],
            "added_at": r[8],
            "status": r[9],
        }
        for r in rows
    ]


def set_active_review(review_id: Optional[str]) -> Dict[str, Any]:
    _ensure_tables()
    conn = _db.get_db()

    if review_id is None:
        with _lock:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('active_review_id', NULL)"
            )
            conn.commit()
        return {"active_review_id": None, "message": "Auto-logging deactivated"}

    with _lock:
        row = conn.execute(
            "SELECT id FROM reviews WHERE id = ?", (review_id,)
        ).fetchone()
    if row is None:
        return {"error": f"Review not found: {review_id}"}

    with _lock:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('active_review_id', ?)",
            (review_id,),
        )
        conn.commit()
    return {
        "active_review_id": review_id,
        "message": f"Auto-logging activated for review {review_id}",
    }


def get_active_review() -> Optional[str]:
    try:
        _ensure_tables()
        conn = _db.get_db()
        with _lock:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = 'active_review_id'"
            ).fetchone()
        if row and row[0]:
            return row[0]
        return None
    except Exception:
        return None


def update_search_new_count(search_id: str, new_count: int) -> None:
    """Update the result_count_new for a search after dedup is computed."""
    conn = _db.get_db()
    with _lock:
        conn.execute(
            "UPDATE review_searches SET result_count_new = ? WHERE id = ?",
            (new_count, search_id),
        )
        conn.commit()


def prisma_counts(review_id: str) -> Dict[str, Any]:
    _ensure_tables()
    conn = _db.get_db()

    with _lock:
        row = conn.execute(
            "SELECT id FROM reviews WHERE id = ?", (review_id,)
        ).fetchone()
        if row is None:
            return {"error": f"Review not found: {review_id}"}

        search_rows = conn.execute(
            "SELECT source, COUNT(*), SUM(result_count_raw) FROM review_searches WHERE review_id = ? GROUP BY source",
            (review_id,),
        ).fetchall()

        total_raw = conn.execute(
            "SELECT COALESCE(SUM(result_count_raw), 0) FROM review_searches WHERE review_id = ?",
            (review_id,),
        ).fetchone()[0]

        total_unique = conn.execute(
            "SELECT COUNT(*) FROM review_papers WHERE review_id = ?",
            (review_id,),
        ).fetchone()[0]

        status_rows = conn.execute(
            "SELECT status, COUNT(*) FROM review_papers WHERE review_id = ? GROUP BY status",
            (review_id,),
        ).fetchall()

    databases = {}
    other_methods = {}
    for source, search_count, record_sum in search_rows:
        entry = {"searches": search_count, "records": int(record_sum or 0)}
        if source == "snowball":
            other_methods["snowball"] = entry
        elif source == "smart_search":
            databases["smart_search"] = entry
        else:
            databases[source] = entry

    status_counts = dict(status_rows)

    return {
        "identification": {
            "databases": databases,
            "other_methods": other_methods,
            "total_records": int(total_raw),
        },
        "duplicates_removed": int(total_raw) - total_unique,
        "unique_records": total_unique,
        "screening": {
            "screened": total_unique,
            "screened_out": status_counts.get("screened_out", 0),
            "sought_for_retrieval": status_counts.get("screened_in", 0),
        },
        "included": status_counts.get("included", 0),
    }


def _extract_doi(paper: Dict) -> str:
    doi = paper.get("doi", "") or ""
    if doi:
        doi = doi.replace("https://doi.org/", "").strip()
    return doi
