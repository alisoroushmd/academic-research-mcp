"""
Local SQLite cache for academic research API responses.

Caches paper metadata, search results, and author profiles to avoid
redundant API calls. Papers that appear across multiple searches
(landmark studies, your own work, frequently cited references) are
fetched once and served from cache thereafter.

Cache is stored at ~/.cache/academic-research-mcp/cache.db by default.
Set ACADEMIC_CACHE_DIR to override.
"""

import functools
import hashlib
import json
import os
import sqlite3
import threading
import time
from typing import Any, Dict, Optional

# Default TTL: 24 hours for search results, 7 days for paper details
SEARCH_TTL = 24 * 60 * 60       # 24 hours
PAPER_TTL = 7 * 24 * 60 * 60    # 7 days
AUTHOR_TTL = 3 * 24 * 60 * 60   # 3 days

# Singleton connection and lock
_conn: Optional[sqlite3.Connection] = None
_lock = threading.Lock()


def _get_cache_path() -> str:
    """Get cache DB path at runtime (not import time)."""
    cache_dir = os.environ.get(
        "ACADEMIC_CACHE_DIR",
        os.path.expanduser("~/.cache/academic-research-mcp"),
    )
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, "cache.db")


def _get_db() -> sqlite3.Connection:
    """Get or create the singleton cache database connection."""
    global _conn
    if _conn is not None:
        return _conn

    with _lock:
        # Double-check after acquiring lock
        if _conn is not None:
            return _conn

        db_path = _get_cache_path()
        conn = sqlite3.connect(db_path, timeout=5, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                category TEXT NOT NULL,
                created_at REAL NOT NULL,
                ttl REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cache_category
            ON cache(category)
        """)
        conn.commit()
        _conn = conn

    return _conn


def make_key(prefix: str, *args, **kwargs) -> str:
    """Generate a deterministic cache key from function arguments."""
    raw = json.dumps({"prefix": prefix, "args": args, "kwargs": kwargs}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def get(key: str) -> Optional[Any]:
    """
    Get a value from cache if it exists and hasn't expired.

    Parameters:
        key: Cache key.

    Returns:
        Cached value or None if not found/expired.
    """
    try:
        conn = _get_db()
        with _lock:
            cursor = conn.execute(
                "SELECT value, created_at, ttl FROM cache WHERE key = ?",
                (key,),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        value, created_at, ttl = row
        if time.time() - created_at > ttl:
            _delete(key)
            return None

        return json.loads(value)
    except Exception:
        return None


def put(key: str, value: Any, category: str = "general", ttl: float = SEARCH_TTL) -> None:
    """
    Store a value in cache.

    Parameters:
        key: Cache key.
        value: Value to cache (must be JSON-serializable).
        category: Category for grouping (e.g., "search", "paper", "author").
        ttl: Time-to-live in seconds.
    """
    try:
        conn = _get_db()
        with _lock:
            conn.execute(
                """INSERT OR REPLACE INTO cache (key, value, category, created_at, ttl)
                   VALUES (?, ?, ?, ?, ?)""",
                (key, json.dumps(value), category, time.time(), ttl),
            )
            conn.commit()
    except Exception:
        pass  # Cache failures should never break the main flow


def _delete(key: str) -> None:
    """Delete a cache entry."""
    try:
        conn = _get_db()
        with _lock:
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            conn.commit()
    except Exception:
        pass


def clear(category: Optional[str] = None) -> int:
    """
    Clear cache entries.

    Parameters:
        category: If provided, only clear entries in this category.
                  Otherwise clear everything.

    Returns:
        Number of entries cleared.
    """
    try:
        conn = _get_db()
        with _lock:
            if category:
                cursor = conn.execute(
                    "DELETE FROM cache WHERE category = ?", (category,)
                )
            else:
                cursor = conn.execute("DELETE FROM cache")
            count = cursor.rowcount
            conn.commit()
        return count
    except Exception:
        return 0


def stats() -> Dict[str, Any]:
    """
    Get cache statistics.

    Returns:
        Dict with total entries, entries by category, and cache size.
    """
    try:
        conn = _get_db()
        with _lock:
            total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]

            categories = {}
            for row in conn.execute(
                "SELECT category, COUNT(*) FROM cache GROUP BY category"
            ):
                categories[row[0]] = row[1]

            expired = conn.execute(
                "SELECT COUNT(*) FROM cache WHERE (? - created_at) > ttl",
                (time.time(),),
            ).fetchone()[0]

        db_path = _get_cache_path()
        size_bytes = os.path.getsize(db_path) if os.path.exists(db_path) else 0

        return {
            "total_entries": total,
            "expired_entries": expired,
            "active_entries": total - expired,
            "by_category": categories,
            "cache_size_mb": round(size_bytes / (1024 * 1024), 2),
            "cache_path": db_path,
        }
    except Exception as e:
        return {"error": str(e)}


def cleanup() -> int:
    """
    Remove expired cache entries.

    Returns:
        Number of entries removed.
    """
    try:
        conn = _get_db()
        with _lock:
            cursor = conn.execute(
                "DELETE FROM cache WHERE (? - created_at) > ttl",
                (time.time(),),
            )
            count = cursor.rowcount
            conn.commit()
        return count
    except Exception:
        return 0


# --- Decorator for easy caching ---

def cached(category: str = "general", ttl: float = SEARCH_TTL):
    """
    Decorator that caches function results.

    Usage:
        @cached(category="search", ttl=SEARCH_TTL)
        def search_papers(query, num_results=10):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = make_key(func.__name__, *args, **kwargs)
            result = get(key)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            put(key, result, category=category, ttl=ttl)
            return result
        return wrapper
    return decorator
