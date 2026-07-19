# -*- coding: utf-8 -*-
"""
db.py — MongoDB shim.

All data access logic lives in mongo_db.py.
This module re-exports everything so that `import db` throughout the codebase
works unchanged — no sys.modules injection required.

To run against a real MongoDB:  docker compose up -d
"""

from mongo_db import *  # noqa: F401, F403
from mongo_db import (  # noqa: F401  (explicit re-export for IDEs + type checkers)
    MONGO_URI,
    MONGO_DB_NAME,
    HAS_PYMONGO,
    get_mongo_client,
    is_mongo_available,
    _lock,
    load_settings,
    save_setting,
    get_company_profile,
    save_company_profile,
    load_all_tenders,
    save_all_tenders,
    upsert_tender,
    upsert_tenders,
    upsert_tender_field,
    get_tender,
    delete_tenders,
    set_extra_field,
    get_extra_fields,
    save_bid_result,
    get_bid_result,
    get_all_bid_results,
    save_bid_competitors,
    get_bid_competitors,
    get_cached_classification,
    set_cached_classification,
    get_classification,
    save_classification,
    text_search_tenders,
    get_result_analytics,
    auto_assign_matrix_fields,
    load_all_products,
    save_product,
    init_db_path,
    get_resolved_db_path,
    get_configured_db_path,
    save_configured_db_path,
    init_db_connection,
    apply_active_learning_from_comments,
    apply_value_mappings,
    DEFAULT_COMPANY_PROFILE,
    DB_FILE,
    COLUMNS,
)

# ── backward-compat stubs (previously SQLite-specific) ────────────────────────
# These attributes are read/written by test setUp/tearDown.
# In the MongoDB world they are no-ops — real isolation is handled by mongomock.
SETTINGS_FILE = None      # settings are stored in the MongoDB settings collection
DEFAULT_DB_FILE = DB_FILE  # kept for any code that references it
