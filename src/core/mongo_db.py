# -*- coding: utf-8 -*-
"""
mongo_db.py — MongoDB backend for TenderTracker.

Provides the same public API as db.py so all callers (import db) work
unchanged when the router in db.py delegates here.

Document schema (flexible — any extra fields are allowed):
{
    "_id":           bid_no (string),
    "bid_no":        str,
    ...standard fields...,
    "extra_fields":  {},           # arbitrary per-tender extras
    "bid_result":    {...},        # embedded outcome sub-document
    "competitors":   [...],        # embedded competitor list
    "embedding":     [float, ...], # FAISS vector (stored for reference)
    "tags":          [str, ...],
}

Settings (user preferences, company profile, etc.) are stored in a
separate `settings` collection as { _id: key, value: ... } documents.
"""

import threading
import json
from datetime import datetime
from typing import Optional

try:
    import pymongo
    from pymongo import MongoClient, ASCENDING, TEXT
    from pymongo.errors import ServerSelectionTimeoutError, PyMongoError
    HAS_PYMONGO = True
except ImportError:
    HAS_PYMONGO = False

# ─── Connection config ────────────────────────────────────────────────────────

MONGO_URI      = "mongodb://localhost:27017/"
MONGO_DB_NAME  = "tendertracker"
CONNECT_TIMEOUT_MS = 3000

_client: Optional["MongoClient"] = None
_db_handle = None
_lock = threading.RLock()
_connected = False


def get_mongo_client():
    """Return a cached MongoClient, creating it on first call."""
    global _client, _db_handle, _connected
    if _client is not None:
        return _client, _db_handle
    if not HAS_PYMONGO:
        raise RuntimeError("pymongo is not installed. Run: pip install pymongo")
    with _lock:
        if _client is None:
            _client = MongoClient(
                MONGO_URI,
                serverSelectionTimeoutMS=CONNECT_TIMEOUT_MS,
                connectTimeoutMS=CONNECT_TIMEOUT_MS,
            )
            # Ping to verify connection
            _client.admin.command("ping")
            _db_handle = _client[MONGO_DB_NAME]
            _init_collections(_db_handle)
            _connected = True
    return _client, _db_handle


def is_mongo_available() -> bool:
    """Return True if MongoDB can be reached."""
    try:
        get_mongo_client()
        return True
    except Exception:
        return False


def _init_collections(mdb):
    """Create indexes on first use."""
    bids = mdb["bids"]
    # Unique index on bid_no (also the _id)
    bids.create_index([("bid_no", ASCENDING)], unique=True, background=True)
    bids.create_index([("dept", ASCENDING)], background=True)
    bids.create_index([("category", ASCENDING)], background=True)
    bids.create_index([("end_date", ASCENDING)], background=True)
    bids.create_index([("sugar_mill", ASCENDING)], background=True)
    bids.create_index([("item_category", ASCENDING)], background=True)
    bids.create_index([("filing_status", ASCENDING)], background=True)
    bids.create_index([("is_want", ASCENDING)], background=True)
    # Full-text search index on key fields
    try:
        bids.create_index(
            [("items", TEXT), ("category", TEXT), ("dept", TEXT),
             ("organisation", TEXT), ("remarks", TEXT)],
            name="bids_text_search",
            background=True,
        )
    except Exception:
        pass  # already exists or not supported


# ─── Settings ─────────────────────────────────────────────────────────────────

def load_settings() -> dict:
    """Load all settings from MongoDB settings collection."""
    try:
        _, mdb = get_mongo_client()
        doc = mdb["settings"].find_one({"_id": "global"})
        return doc.get("data", {}) if doc else {}
    except Exception:
        return {}


def save_setting(key: str, value) -> bool:
    """Save a single setting key-value pair."""
    try:
        _, mdb = get_mongo_client()
        mdb["settings"].update_one(
            {"_id": "global"},
            {"$set": {f"data.{key}": value}},
            upsert=True,
        )
        return True
    except Exception:
        return False


# Company profile helpers
DEFAULT_COMPANY_PROFILE = {
    "categories": [], "max_est_value": 0, "min_exp_years": 0,
    "min_turnover": 0, "location_keywords": [], "is_mse": False,
    "is_startup": False, "max_emd": -1,
}

def get_company_profile() -> dict:
    settings = load_settings()
    profile = settings.get("company_profile")
    if not isinstance(profile, dict):
        return DEFAULT_COMPANY_PROFILE.copy()
    merged = DEFAULT_COMPANY_PROFILE.copy()
    merged.update(profile)
    return merged

def save_company_profile(profile_dict: dict) -> bool:
    if not isinstance(profile_dict, dict):
        return False
    return save_setting("company_profile", profile_dict)


# ─── Tender CRUD ──────────────────────────────────────────────────────────────

def _doc_to_dict(doc: dict) -> dict:
    """Convert a MongoDB document to the standard tender dict the app expects."""
    if doc is None:
        return {}
    d = {k: v for k, v in doc.items() if k != "_id"}
    # Deserialize tags if somehow stored as string
    if isinstance(d.get("tags"), str):
        try:
            d["tags"] = json.loads(d["tags"])
        except Exception:
            d["tags"] = []
    if isinstance(d.get("embedding"), str):
        try:
            d["embedding"] = json.loads(d["embedding"])
        except Exception:
            d["embedding"] = []
    return d


def _dict_to_doc(d: dict) -> dict:
    """Prepare a tender dict for MongoDB storage."""
    doc = dict(d)
    doc["_id"] = doc.get("bid_no", "")
    # Store booleans natively (MongoDB supports them)
    return doc


def load_all_tenders(limit=None, offset=0) -> list:
    """Load tenders from MongoDB with optional pagination."""
    try:
        _, mdb = get_mongo_client()
        cursor = mdb["bids"].find({}, {"embedding": 0})  # exclude heavy embedding
        cursor = cursor.skip(offset)
        if limit is not None:
            cursor = cursor.limit(limit)
        return [_doc_to_dict(doc) for doc in cursor]
    except Exception as e:
        import logger
        logger.log_err(f"mongo load_all_tenders error: {e}")
        return []


def save_all_tenders(records: list) -> bool:
    """Replace ALL tender documents (used for bulk import)."""
    try:
        _, mdb = get_mongo_client()
        col = mdb["bids"]
        col.delete_many({})
        if records:
            col.insert_many([_dict_to_doc(r) for r in records], ordered=False)
        return True
    except Exception as e:
        import logger
        logger.log_err(f"mongo save_all_tenders error: {e}")
        return False


def upsert_tender(record: dict) -> list:
    """Insert or update a single tender. Returns full tender list."""
    bid_no = record.get("bid_no")
    if not bid_no:
        return load_all_tenders()
    try:
        _, mdb = get_mongo_client()
        col = mdb["bids"]
        existing = col.find_one({"_id": bid_no})

        if existing:
            # Merge: only overwrite fields that are non-empty in record,
            # never overwrite a manually-filed status.
            update_fields = {}
            for k, v in record.items():
                if v is None or (isinstance(v, str) and not v.strip()):
                    continue
                if k == "filing_status" and existing.get("filing_status") == "Filed":
                    continue
                update_fields[k] = v
            if update_fields:
                col.update_one({"_id": bid_no}, {"$set": update_fields})
        else:
            doc = _dict_to_doc(record)
            col.insert_one(doc)
    except Exception as e:
        import logger
        logger.log_err(f"mongo upsert_tender error for {bid_no}: {e}")
    return load_all_tenders()


def upsert_tenders(new_records: list) -> list:
    """Bulk insert/update tender records."""
    try:
        _, mdb = get_mongo_client()
        col = mdb["bids"]
        for record in new_records:
            bid_no = record.get("bid_no")
            if not bid_no:
                continue
            existing = col.find_one({"_id": bid_no}, {"filing_status": 1})
            update_fields = {}
            for k, v in record.items():
                if v is None or (isinstance(v, str) and not v.strip()):
                    continue
                if k == "filing_status" and existing and existing.get("filing_status") == "Filed":
                    continue
                update_fields[k] = v
            if update_fields:
                col.update_one({"_id": bid_no}, {"$set": update_fields}, upsert=True)
    except Exception as e:
        import logger
        logger.log_err(f"mongo upsert_tenders error: {e}")
    return load_all_tenders()


def upsert_tender_field(bid_no: str, field: str, value) -> bool:
    """Surgically update a single field for a tender."""
    try:
        _, mdb = get_mongo_client()
        result = mdb["bids"].update_one(
            {"_id": bid_no},
            {"$set": {field: value}},
        )
        return result.matched_count > 0
    except Exception as e:
        import logger
        logger.log_err(f"mongo upsert_tender_field error {bid_no}.{field}: {e}")
        return False


def get_tender(bid_no: str) -> Optional[dict]:
    """Retrieve a single tender by bid_no."""
    try:
        _, mdb = get_mongo_client()
        doc = mdb["bids"].find_one({"_id": bid_no})
        return _doc_to_dict(doc) if doc else None
    except Exception:
        return None


def delete_tenders(bid_numbers: list) -> list:
    """Delete tenders by bid_no list."""
    try:
        _, mdb = get_mongo_client()
        mdb["bids"].delete_many({"_id": {"$in": bid_numbers}})
    except Exception as e:
        import logger
        logger.log_err(f"mongo delete_tenders error: {e}")
    return load_all_tenders()


# ─── Extra / unstructured fields ──────────────────────────────────────────────

def set_extra_field(bid_no: str, key: str, value) -> bool:
    """
    Store an arbitrary extra field on a tender document.
    Use this for any tender-specific data that doesn't fit standard columns.
    e.g. set_extra_field("GEM/...", "warranty_years", "2")
    """
    try:
        _, mdb = get_mongo_client()
        mdb["bids"].update_one(
            {"_id": bid_no},
            {"$set": {f"extra_fields.{key}": value}},
            upsert=False,
        )
        return True
    except Exception:
        return False


def get_extra_fields(bid_no: str) -> dict:
    """Get all extra/unstructured fields for a tender."""
    try:
        _, mdb = get_mongo_client()
        doc = mdb["bids"].find_one({"_id": bid_no}, {"extra_fields": 1})
        return (doc or {}).get("extra_fields", {})
    except Exception:
        return {}


# ─── Bid Result (embedded sub-document) ───────────────────────────────────────

def save_bid_result(bid_no: str, result_dict: dict) -> bool:
    """Upsert bid result as an embedded sub-document on the tender."""
    try:
        _, mdb = get_mongo_client()
        result_dict["recorded_at"] = result_dict.get("recorded_at") or datetime.now().isoformat(timespec="seconds")
        mdb["bids"].update_one(
            {"_id": bid_no},
            {"$set": {"bid_result": result_dict}},
            upsert=False,
        )
        return True
    except Exception as e:
        import logger
        logger.log_err(f"mongo save_bid_result error {bid_no}: {e}")
        return False


def get_bid_result(bid_no: str) -> Optional[dict]:
    """Get the embedded bid result for a tender."""
    try:
        _, mdb = get_mongo_client()
        doc = mdb["bids"].find_one({"_id": bid_no}, {"bid_result": 1})
        return (doc or {}).get("bid_result")
    except Exception:
        return None


def get_all_bid_results() -> dict:
    """Return dict of bid_no -> bid_result for all tenders that have one."""
    try:
        _, mdb = get_mongo_client()
        cursor = mdb["bids"].find(
            {"bid_result": {"$exists": True}},
            {"bid_no": 1, "bid_result": 1},
        )
        return {
            doc["bid_no"]: doc["bid_result"]
            for doc in cursor
            if doc.get("bid_result")
        }
    except Exception:
        return {}


# ─── Competitors (embedded array) ─────────────────────────────────────────────

def save_bid_competitors(bid_no: str, competitors: list) -> bool:
    """Replace competitors array on the tender document."""
    try:
        _, mdb = get_mongo_client()
        mdb["bids"].update_one(
            {"_id": bid_no},
            {"$set": {"competitors": competitors}},
            upsert=False,
        )
        return True
    except Exception as e:
        import logger
        logger.log_err(f"mongo save_bid_competitors error {bid_no}: {e}")
        return False


def get_bid_competitors(bid_no: str) -> list:
    """Get competitors array from the tender document."""
    try:
        _, mdb = get_mongo_client()
        doc = mdb["bids"].find_one({"_id": bid_no}, {"competitors": 1})
        comps = (doc or {}).get("competitors", [])
        return sorted(comps, key=lambda c: c.get("rank", 999))
    except Exception:
        return []


# ─── Cache ────────────────────────────────────────────────────────────────────

def get_cached_classification(cache_key: str) -> Optional[dict]:
    try:
        _, mdb = get_mongo_client()
        doc = mdb["cache"].find_one({"_id": cache_key})
        return doc.get("value") if doc else None
    except Exception:
        return None


def set_cached_classification(cache_key: str, value: dict):
    try:
        _, mdb = get_mongo_client()
        mdb["cache"].update_one(
            {"_id": cache_key},
            {"$set": {"value": value, "created_at": datetime.utcnow()}},
            upsert=True,
        )
    except Exception:
        pass


# ─── Classifications ──────────────────────────────────────────────────────────

def get_classification(bid_no: str) -> Optional[dict]:
    try:
        _, mdb = get_mongo_client()
        doc = mdb["classifications"].find_one({"_id": bid_no})
        return _doc_to_dict(doc) if doc else None
    except Exception:
        return None


def save_classification(cls_data: dict):
    try:
        _, mdb = get_mongo_client()
        bid_no = cls_data.get("bid_no")
        if not bid_no:
            return
        doc = dict(cls_data)
        doc["_id"] = bid_no
        mdb["classifications"].replace_one({"_id": bid_no}, doc, upsert=True)
    except Exception:
        pass


# ─── Text search (uses MongoDB $text index) ───────────────────────────────────

def text_search_tenders(query: str, limit: int = 50) -> list:
    """
    Full-text search across items, category, dept, organisation, remarks.
    Falls back to regex if text index not available.
    """
    try:
        _, mdb = get_mongo_client()
        try:
            cursor = mdb["bids"].find(
                {"$text": {"$search": query}},
                {"score": {"$meta": "textScore"}, "embedding": 0},
            ).sort([("score", {"$meta": "textScore"})]).limit(limit)
            return [_doc_to_dict(doc) for doc in cursor]
        except PyMongoError:
            # Fallback: simple regex
            pattern = {"$regex": query, "$options": "i"}
            cursor = mdb["bids"].find(
                {"$or": [
                    {"items": pattern}, {"category": pattern},
                    {"dept": pattern}, {"organisation": pattern},
                ]},
                {"embedding": 0},
            ).limit(limit)
            return [_doc_to_dict(doc) for doc in cursor]
    except Exception:
        return []


# ─── Analytics helpers ────────────────────────────────────────────────────────

def get_result_analytics() -> dict:
    """
    Return aggregate stats on bid results for the analytics tab.
    {
      "total_with_result": int,
      "won": int, "lost": int, "pending": int,
      "avg_price_gap_pct": float,
      "worst_loss": dict,   # tender with highest price gap %
    }
    """
    try:
        _, mdb = get_mongo_client()
        pipeline = [
            {"$match": {"bid_result": {"$exists": True}}},
            {"$group": {
                "_id": "$bid_result.result",
                "count": {"$sum": 1},
                "avg_gap_pct": {"$avg": "$bid_result.price_gap_pct"},
            }},
        ]
        rows = list(mdb["bids"].aggregate(pipeline))
        stats = {"total_with_result": 0, "won": 0, "lost": 0, "pending": 0, "avg_price_gap_pct": 0.0}
        for row in rows:
            result_type = (row["_id"] or "Pending").lower()
            stats[result_type] = row["count"]
            stats["total_with_result"] += row["count"]
            if result_type == "lost":
                stats["avg_price_gap_pct"] = round(row.get("avg_gap_pct") or 0, 2)
        return stats
    except Exception:
        return {}


# ─── DB path / compatibility stubs ────────────────────────────────────────────
# These are no-ops kept so callers that reference db.DB_FILE or db.init_db_path()
# don't break during the transition.

DB_FILE = "mongodb://localhost:27017/tendertracker"
COLUMNS = []  # MongoDB is schemaless


def init_db_path(custom_path=None):
    pass


def get_resolved_db_path():
    return DB_FILE


def get_configured_db_path():
    return load_settings().get("db_path")


def save_configured_db_path(path):
    return save_setting("db_path", path)


def init_db_connection():
    try:
        get_mongo_client()
    except Exception:
        pass


def apply_active_learning_from_comments():
    """No-op stub — active learning is handled at parse time."""
    pass


def auto_assign_matrix_fields(rec: dict):
    """Assign sugar_mill and item_category by keyword if empty."""
    if not rec.get("sugar_mill"):
        mills = [
            "NAJIBABAD", "ANOOPSHAHR", "SULTANPUR", "NANPARA", "BELRAYAN",
            "SAMPURNANAGAR", "RAMALA", "MORNA", "GHOSI", "NANAUTA", "SEMIKHERA",
            "SARSAWAN", "MAHMUDABAD", "TILHAR", "BISALPUR", "POWAYAN", "PURANPUR",
            "BAGPAT", "GAJRAULLA", "FEDRATION", "CORPORATION", "KAIAMGANJ",
            "SATHIAON", "BUDAUN", "BILASPUR",
        ]
        for field in ("location", "organisation", "comments", "remarks", "dept", "category", "items"):
            val = rec.get(field)
            if val:
                val_upper = str(val).upper()
                found = [m for m in mills if m in val_upper]
                if found:
                    rec["sugar_mill"] = found[0]
                    break

    if not rec.get("item_category"):
        cat_str = rec.get("category") or ""
        item_str = rec.get("items") or ""
        combined = (cat_str + " | " + item_str).lower()
        if any(k in combined for k in ("nickel", "screen")):
            rec["item_category"] = "Nickel screen"
        elif any(k in combined for k in ("packing", "jointing", "gasket", "asbestos")):
            rec["item_category"] = "Packing jointing"
        elif any(k in combined for k in ("light", "led", "flood", "lighting", "fitting")):
            rec["item_category"] = "Light"
        elif any(k in combined for k in ("motor", "induction", "cage")):
            rec["item_category"] = "Motor"
        elif any(k in combined for k in ("cable", "wire", "armoured", "conductor")):
            rec["item_category"] = "Cable"
        elif any(k in combined for k in ("gas", "oxygen", "argon", "cylinder", "co2", "nitrogen")):
            rec["item_category"] = "Gas"
        elif any(k in combined for k in ("vfd", "drive", "frequency")):
            rec["item_category"] = "VFD"
        else:
            rec["item_category"] = "OTHERS"
