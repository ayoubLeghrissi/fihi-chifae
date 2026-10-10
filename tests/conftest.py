"""Test fixtures.

RULE FOR EVERY TEST IN THIS SUITE
---------------------------------
Tests are allowed to run against the real (production) databases, but each
test MUST delete everything it created: rows in the live database, rows in
the archive database and uploaded image files. Nothing a test adds may stay.

This is enforced automatically, not left to each test:

- ``_cleanup_after_each_test`` (autouse) snapshots every table of both
  databases and the upload directory before a test, and afterwards deletes
  every row and file that did not exist before - even when the test fails.
- ``_verify_databases_untouched`` (session) compares row counts at the start
  and at the end of the whole run and fails the run if anything was left.

Tests must not *modify* pre-existing rows (only rows they created), because
the snapshot restores additions, not edits.
"""

import os
import sqlite3

import pytest

from app import config
from app import db as database


def _tables(path):
    with sqlite3.connect(path) as conn:
        return [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]


def _snapshot():
    snap = {}
    for path in (config.DB_FILE, config.ARCHIVE_DB_FILE):
        with sqlite3.connect(path) as conn:
            for table in _tables(path):
                snap[(path, table)] = {r[0] for r in conn.execute(f"SELECT rowid FROM {table}")}
    files = set(os.listdir(config.UPLOAD_DIR)) if os.path.isdir(config.UPLOAD_DIR) else set()
    return snap, files


def _restore(snapshot):
    snap, files = snapshot
    with database.db_lock:
        for path in (config.DB_FILE, config.ARCHIVE_DB_FILE):
            with sqlite3.connect(path, timeout=10) as conn:
                for table in _tables(path):
                    before = snap.get((path, table), set())
                    created = [
                        r[0]
                        for r in conn.execute(f"SELECT rowid FROM {table}")
                        if r[0] not in before
                    ]
                    conn.executemany(f"DELETE FROM {table} WHERE rowid=?", [(i,) for i in created])
    if os.path.isdir(config.UPLOAD_DIR):
        for name in set(os.listdir(config.UPLOAD_DIR)) - files:
            os.remove(os.path.join(config.UPLOAD_DIR, name))


def _counts():
    out = {}
    for path in (config.DB_FILE, config.ARCHIVE_DB_FILE):
        with sqlite3.connect(path) as conn:
            for table in _tables(path):
                out[(os.path.basename(path), table)] = conn.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]
    return out


@pytest.fixture(scope="session", autouse=True)
def _verify_databases_untouched():
    database.init_db()  # schema/migrations first, so they are not mistaken for test data
    start = _counts()
    yield
    end = _counts()
    leftovers = {k: (start.get(k, 0), v) for k, v in end.items() if start.get(k, 0) != v}
    assert not leftovers, f"tests left data behind (table: before -> after): {leftovers}"


@pytest.fixture(autouse=True)
def _cleanup_after_each_test():
    snapshot = _snapshot()
    try:
        yield
    finally:
        _restore(snapshot)


@pytest.fixture
def category():
    """A throw-away category (removed automatically after the test)."""
    from app import catalog

    return catalog.create_category(f"pytest-cat-{os.urandom(4).hex()}")


@pytest.fixture
def product(category):
    """A throw-away product priced 100 MAD per kg (removed automatically)."""
    from app import catalog

    return catalog.add_product(f"pytest-prod-{os.urandom(4).hex()}", category["slug"], 100.0, "")
