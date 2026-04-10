"""
Shared SQLite connection module for academic-research-mcp.

Provides a singleton database connection (WAL mode, thread-safe) used by
cache.py and review_manager.py so both modules share a single connection
to the same on-disk database file.

The DB file lives at:
    $ACADEMIC_CACHE_DIR/cache.db   (if env var is set)
    ~/.cache/academic-research-mcp/cache.db  (default)
"""

import os
import sqlite3
import threading
from typing import Optional

_conn: Optional[sqlite3.Connection] = None
_lock = threading.Lock()


def get_db_path() -> str:
    """Return the path to the SQLite database file.

    Respects the ACADEMIC_CACHE_DIR environment variable; falls back to
    ~/.cache/academic-research-mcp.  The directory is created if it does
    not already exist.
    """
    cache_dir = os.environ.get(
        "ACADEMIC_CACHE_DIR",
        os.path.expanduser("~/.cache/academic-research-mcp"),
    )
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, "cache.db")


def get_db() -> sqlite3.Connection:
    """Return the singleton SQLite connection, creating it on first call.

    The connection is opened with:
    - WAL journal mode for concurrent readers.
    - check_same_thread=False so it can be shared across threads (callers
      must acquire _lock around writes).
    - A 5-second busy timeout.
    """
    global _conn
    if _conn is not None:
        return _conn

    with _lock:
        # Double-checked locking: another thread may have initialised while
        # we were waiting for the lock.
        if _conn is not None:
            return _conn

        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=5, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.commit()
        _conn = conn

    return _conn
