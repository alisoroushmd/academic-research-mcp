"""
Tests for db.py — shared SQLite connection module.
"""

import sqlite3

import db


def test_get_db_returns_connection(tmp_db_dir):
    conn = db.get_db()
    assert isinstance(conn, sqlite3.Connection)


def test_get_db_creates_file(tmp_db_dir):
    db.get_db()
    db_path = db.get_db_path()
    import os

    assert os.path.exists(db_path)


def test_get_db_singleton(tmp_db_dir):
    conn1 = db.get_db()
    conn2 = db.get_db()
    assert conn1 is conn2


def test_get_db_wal_mode(tmp_db_dir):
    conn = db.get_db()
    row = conn.execute("PRAGMA journal_mode").fetchone()
    assert row[0] == "wal"
