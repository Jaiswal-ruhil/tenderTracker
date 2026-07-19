# -*- coding: utf-8 -*-
"""
tests/conftest.py
-----------------
Pytest configuration: replace pymongo with an in-memory mongomock instance
before every test so no Docker container is needed during the test suite.

Each test gets a completely fresh, isolated MongoDB (mongomock) — the same
isolation that SQLite temp-file overrides previously provided.
"""

import sys
import os

# Ensure src paths are on sys.path (mirrors what each test file does)
_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, os.path.join(_ROOT, "src", "core"))
sys.path.insert(0, os.path.join(_ROOT, "src", "gui"))
sys.path.insert(0, os.path.join(_ROOT, "src", "core", "parsers"))
sys.path.insert(0, os.path.join(_ROOT, "src", "core", "ai"))
sys.path.insert(0, os.path.join(_ROOT, "src", "core", "workflow"))
sys.path.insert(0, os.path.join(_ROOT, "src", "mcp"))

import pytest

try:
    import mongomock
    _HAS_MONGOMOCK = True
except ImportError:
    _HAS_MONGOMOCK = False


def _reset_mongo_module():
    """Reset mongo_db globals to a fresh in-memory mongomock instance."""
    import mongo_db  # imported here so path is already set

    if not _HAS_MONGOMOCK:
        # If mongomock is not installed, let tests run against real MongoDB
        # (or fail gracefully if Docker is not running).
        return

    client = mongomock.MongoClient()
    mdb = client[mongo_db.MONGO_DB_NAME]
    mongo_db._client = client
    mongo_db._db_handle = mdb
    mongo_db._connected = True
    mongo_db._init_collections(mdb)


@pytest.fixture(autouse=True)
def _fresh_mongo_per_test():
    """Auto-used fixture: reset mongo_db to a clean state before every test."""
    _reset_mongo_module()
    yield
    # Teardown: reset state so the next test starts clean
    if _HAS_MONGOMOCK:
        import mongo_db
        mongo_db._client = None
        mongo_db._db_handle = None
        mongo_db._connected = False
