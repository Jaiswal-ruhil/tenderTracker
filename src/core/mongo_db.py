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
import os
import sys
import time
import subprocess
from datetime import datetime
from typing import Optional, Callable

try:
    import pymongo
    from pymongo import MongoClient, ASCENDING, TEXT
    from pymongo.errors import ServerSelectionTimeoutError, PyMongoError
    HAS_PYMONGO = True
except ImportError:
    HAS_PYMONGO = False

# ─── Connection config ────────────────────────────────────────────────────────

MONGO_URI                  = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME              = os.getenv("MONGO_DB_NAME", "tendertracker")
CONNECT_TIMEOUT_MS         = int(os.getenv("MONGO_CONNECT_TIMEOUT_MS", "3000"))

BIDS_COLLECTION            = os.getenv("MONGO_BIDS_COLLECTION", "bids")
SETTINGS_COLLECTION        = os.getenv("MONGO_SETTINGS_COLLECTION", "settings")
PRODUCTS_COLLECTION        = os.getenv("MONGO_PRODUCTS_COLLECTION", "products")
CACHE_COLLECTION           = os.getenv("MONGO_CACHE_COLLECTION", "cache")
CLASSIFICATIONS_COLLECTION = os.getenv("MONGO_CLASSIFICATIONS_COLLECTION", "classifications")

INGEST_BATCH_SIZE          = int(os.getenv("MONGO_INGEST_BATCH_SIZE", "500"))

_client: Optional["MongoClient"] = None
_db_handle = None
_lock = threading.RLock()
_connected = False


def get_mongo_client():
    """Return a cached MongoClient, creating it on first call."""
    global _client, _db_handle, _connected
    if _client is not None and _connected:
        try:
            _client.admin.command("ping")
            return _client, _db_handle
        except Exception:
            _client = None
            _db_handle = None
            _connected = False

    if not HAS_PYMONGO:
        raise RuntimeError("pymongo is not installed. Run: pip install pymongo")
    with _lock:
        if _client is None or not _connected:
            try:
                client = MongoClient(
                    MONGO_URI,
                    serverSelectionTimeoutMS=CONNECT_TIMEOUT_MS,
                    connectTimeoutMS=CONNECT_TIMEOUT_MS,
                )
                client.admin.command("ping")
                db_h = client[MONGO_DB_NAME]
                _init_collections(db_h)
                _client = client
                _db_handle = db_h
                _connected = True
            except Exception:
                _client = None
                _db_handle = None
                _connected = False
                raise
    return _client, _db_handle


def is_mongo_available() -> bool:
    """Return True if MongoDB can be reached."""
    global _client, _db_handle, _connected
    try:
        client, _ = get_mongo_client()
        client.admin.command("ping")
        return True
    except Exception:
        _client = None
        _db_handle = None
        _connected = False
        return False


def ensure_mongo_container_running(max_wait_seconds: int = 35, status_callback: Optional[Callable[[str], None]] = None) -> bool:
    """Ensure MongoDB is available. If not, attempt to start the Docker container automatically."""
    def log(msg: str):
        print(f"[TenderTracker] {msg}")
        if status_callback:
            try:
                status_callback(msg)
            except Exception:
                pass

    if is_mongo_available():
        return True

    log("MongoDB is not running. Attempting to start containers via Docker...")

    # Helper function to run docker compose up -d
    def run_docker_compose():
        project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        compose_file = os.path.join(project_dir, "docker-compose.yml")
        cwd = project_dir if os.path.exists(compose_file) else os.getcwd()

        kwargs = {
            "cwd": cwd,
            "capture_output": True,
            "text": True,
            "timeout": 15,
        }
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        for cmd in [
            ["docker", "compose", "up", "-d"],
            ["docker-compose", "up", "-d"],
        ]:
            try:
                res = subprocess.run(cmd, **kwargs)
                if res.returncode == 0:
                    return "ok", res.stdout
                err_msg = (res.stderr or res.stdout or "").strip()
                err_lower = err_msg.lower()
                if "daemon is not running" in err_lower or "npipe" in err_lower or "connect" in err_lower:
                    return "daemon_down", err_msg
            except FileNotFoundError:
                continue
            except Exception as e:
                return "error", str(e)
        return "error", "Docker CLI not found."

    status, msg = run_docker_compose()

    # If daemon is down, attempt to launch Docker Desktop if on Windows
    if status == "daemon_down" and os.name == "nt":
        docker_desktop_path = r"C:\Program Files\Docker\Docker\Docker Desktop.exe"
        if os.path.exists(docker_desktop_path):
            log("Docker Desktop is not running. Starting Docker Desktop...")
            try:
                os.startfile(docker_desktop_path)
            except Exception as e:
                log(f"Failed to start Docker Desktop: {e}")

        log("Waiting for Docker daemon to become ready...")
        start_daemon_wait = time.time()
        while time.time() - start_daemon_wait < 30:
            time.sleep(2)
            status, msg = run_docker_compose()
            if status == "ok":
                break

    if status != "ok":
        log(f"Docker compose attempt: {msg}")

    # Wait for MongoDB service to respond
    log("Waiting for MongoDB service to initialize...")
    start_time = time.time()
    while time.time() - start_time < max_wait_seconds:
        if is_mongo_available():
            log("MongoDB started successfully!")
            return True
        time.sleep(1)

    return is_mongo_available()


def _init_collections(mdb):
    """Create indexes on first use."""
    bids = mdb[BIDS_COLLECTION]
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
        doc = mdb[SETTINGS_COLLECTION].find_one({"_id": "global"})
        return doc.get("data", {}) if doc else {}
    except Exception:
        return {}


def save_setting(key: str, value) -> bool:
    """Save a single setting key-value pair."""
    try:
        _, mdb = get_mongo_client()
        mdb[SETTINGS_COLLECTION].update_one(
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
    if "bid_no" not in d and "_id" in doc:
        d["bid_no"] = doc["_id"]
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


def load_all_tenders(limit=None, offset=0, include_embeddings=False) -> list:
    """Load tenders from MongoDB with optional pagination."""
    try:
        _, mdb = get_mongo_client()
        projection = {} if include_embeddings else {"embedding": 0}
        cursor = mdb[BIDS_COLLECTION].find({}, projection)
        cursor = cursor.skip(offset)
        if limit is not None:
            cursor = cursor.limit(limit)
        return [_doc_to_dict(doc) for doc in cursor]
    except Exception as e:
        import logger
        logger.log_err(f"mongo load_all_tenders error: {e}")
        return []


def save_all_tenders(records: list) -> bool:
    """Replace ALL tender documents while preserving un-rendered fields like embeddings."""
    try:
        _, mdb = get_mongo_client()
        col = mdb[BIDS_COLLECTION]
        
        # Get all new bid_nos to identify deleted ones
        new_bid_nos = [r.get("bid_no") for r in records if r.get("bid_no")]
        
        # Delete any tenders that are no longer in the records list
        col.delete_many({"_id": {"$nin": new_bid_nos}})
        
        for r in records:
            bid_no = r.get("bid_no")
            if not bid_no:
                continue
            doc = _dict_to_doc(r)
            # Remove _id so we don't try to change it in $set
            doc.pop("_id", None)
            col.update_one({"_id": bid_no}, {"$set": doc}, upsert=True)
            
        return True
    except Exception as e:
        import logger
        logger.log_err(f"mongo save_all_tenders error: {e}")
        return False


def ingest_tenders_batch(records: list, batch_size: Optional[int] = None, skip_unify: bool = False) -> dict:
    """
    High-performance bulk ingestion of tender records into MongoDB.
    Uses bulk_write with UpdateOne(..., upsert=True) in batches to minimize network roundtrips.

    Args:
        records: List of tender dictionaries to ingest.
        batch_size: Max documents per bulk operation batch (default from INGEST_BATCH_SIZE).
        skip_unify: If True, skips fuzzy organization unification for raw performance.

    Returns:
        dict with metrics: {"total": int, "processed": int, "upserted": int, "modified": int, "errors": list}
    """
    if not records:
        return {"total": 0, "processed": 0, "upserted": 0, "modified": 0, "errors": []}

    batch_size = batch_size or INGEST_BATCH_SIZE
    stats = {"total": len(records), "processed": 0, "upserted": 0, "modified": 0, "errors": []}

    try:
        from pymongo import UpdateOne
        from pymongo.errors import BulkWriteError
    except ImportError:
        import logger
        logger.log_err("pymongo not available for batch ingestion")
        # Fallback to sequential upserts if PyMongo bulk_write isn't available
        for rec in records:
            upsert_tender(rec)
        stats["processed"] = len(records)
        return stats

    try:
        _, mdb = get_mongo_client()
        col = mdb[BIDS_COLLECTION]

        for i in range(0, len(records), batch_size):
            chunk = records[i : i + batch_size]
            operations = []
            valid_bid_nos = []
            chunk_records_by_bid = {}

            for r in chunk:
                bid_no = r.get("bid_no")
                if not bid_no:
                    continue
                if not skip_unify:
                    r = unify_organization_names(r)
                r = apply_value_mappings(r)
                valid_bid_nos.append(bid_no)
                chunk_records_by_bid[bid_no] = r

            if not valid_bid_nos:
                continue

            # Fetch existing records in chunk to preserve 'Filed' filing_status
            existing_docs = {
                doc["_id"]: doc
                for doc in col.find({"_id": {"$in": valid_bid_nos}}, {"filing_status": 1})
            }

            for bid_no, record in chunk_records_by_bid.items():
                existing = existing_docs.get(bid_no)
                update_fields = {}
                for k, v in record.items():
                    if v is None or (isinstance(v, str) and not v.strip()):
                        continue
                    if k == "filing_status" and existing and existing.get("filing_status") == "Filed":
                        continue
                    update_fields[k] = v

                if update_fields:
                    operations.append(UpdateOne({"_id": bid_no}, {"$set": update_fields}, upsert=True))

            if operations:
                try:
                    res = col.bulk_write(operations, ordered=False)
                    stats["processed"] += len(operations)
                    stats["upserted"] += getattr(res, "upserted_count", 0)
                    stats["modified"] += getattr(res, "modified_count", 0)
                except BulkWriteError as bwe:
                    stats["processed"] += bwe.details.get("nInserted", 0) + bwe.details.get("nModified", 0)
                    stats["errors"].append(str(bwe.details))
                    import logger
                    logger.log_err(f"mongo bulk_write partial error: {bwe.details}")
                except Exception as b_err:
                    # Fallback for mock/test environments (e.g. mongomock) that lack full bulk_write argument support
                    for op in operations:
                        try:
                            filter_doc = getattr(op, "_filter", {})
                            update_doc = getattr(op, "_doc", {})
                            upsert_val = getattr(op, "_upsert", True)
                            res = col.update_one(filter_doc, update_doc, upsert=upsert_val)
                            if getattr(res, "upserted_id", None):
                                stats["upserted"] += 1
                            elif getattr(res, "modified_count", 0):
                                stats["modified"] += 1
                            stats["processed"] += 1
                        except Exception as u_err:
                            stats["errors"].append(str(u_err))

    except Exception as e:
        import logger
        logger.log_err(f"mongo ingest_tenders_batch error: {e}")
        stats["errors"].append(str(e))

    return stats


def upsert_tender(record: dict) -> list:
    """Insert or update a single tender. Returns full tender list."""
    bid_no = record.get("bid_no")
    if not bid_no:
        return load_all_tenders()
    try:
        record = unify_organization_names(record)
        record = apply_value_mappings(record)
        _, mdb = get_mongo_client()
        col = mdb[BIDS_COLLECTION]
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
    """Bulk insert/update tender records using batch ingestion."""
    if new_records:
        ingest_tenders_batch(new_records)
    return load_all_tenders()


def upsert_tender_field(bid_no: str, field: str, value) -> bool:
    """Surgically update a single field for a tender."""
    try:
        _, mdb = get_mongo_client()
        result = mdb[BIDS_COLLECTION].update_one(
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
        doc = mdb[BIDS_COLLECTION].find_one({"_id": bid_no})
        return _doc_to_dict(doc) if doc else None
    except Exception:
        return None


def delete_tenders(bid_numbers: list) -> list:
    """Delete tenders by bid_no list."""
    try:
        _, mdb = get_mongo_client()
        mdb[BIDS_COLLECTION].delete_many({"_id": {"$in": bid_numbers}})
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


# ─── Products ─────────────────────────────────────────────────────────────────

def _product_doc_to_dict(d: dict) -> dict:
    if not d:
        return {}
    d = dict(d)
    if "_id" in d:
        d["product_id"] = d.pop("_id")
    return d


def load_all_products() -> list:
    """Load all company products from MongoDB."""
    try:
        _, mdb = get_mongo_client()
        cursor = mdb["products"].find({})
        return [_product_doc_to_dict(doc) for doc in cursor]
    except Exception as e:
        import logger
        logger.log_err(f"mongo load_all_products error: {e}")
        return []


def save_product(prod: dict) -> bool:
    """Insert or replace a company product in MongoDB."""
    product_id = prod.get("product_id")
    if not product_id:
        return False
    try:
        _, mdb = get_mongo_client()
        doc = dict(prod)
        doc["_id"] = product_id
        mdb["products"].replace_one({"_id": product_id}, doc, upsert=True)
        return True
    except Exception as e:
        import logger
        logger.log_err(f"mongo save_product error for {product_id}: {e}")
        return False


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
        except Exception:
            # Fallback: simple regex (e.g. under mongomock or if text index is missing)
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


def apply_value_mappings(record: dict) -> dict:
    """
    Applies custom user field mapping rules (e.g. mapping phrases to keys for specific headers)
    to a tender record.
    """
    settings = load_settings()
    mappings = settings.get("value_mappings", [])
    if not mappings:
        return record

    def normalize_whitespace(s):
        if not s:
            return ""
        return " ".join(str(s).split()).lower()

    for rule in mappings:
        field = rule.get("field")
        phrase = rule.get("phrase")
        key = rule.get("key")
        
        if field and phrase and key and field in record:
            val = record[field]
            if val and str(val).strip():
                if normalize_whitespace(phrase) in normalize_whitespace(val):
                    record[field] = key
                    
    return record


def apply_active_learning_from_comments():
    """
    Scans all tender records in the database for comment instructions
    (e.g., 'this should map organization to X') and automatically
    updates the record and adds global value mapping rules to settings.
    """
    import re
    import logger
    try:
        _, mdb = get_mongo_client()
        col = mdb["bids"]
        # Find all bids with a non-empty comments field
        cursor = col.find({"comments": {"$exists": True, "$ne": ""}})
        
        settings_changed = False
        settings = load_settings()
        mappings = settings.get("value_mappings", [])
        
        for doc in cursor:
            bid_no = doc.get("_id")
            comment = doc.get("comments", "")
            dept = doc.get("dept", "")
            organisation = doc.get("organisation", "")
            category = doc.get("category", "")
            
            match = re.search(
                r'(?:thi[s]?\s+)?shoud?\s+map\s+(organisation|organization|dept|department|category|location|office|ministry)\s+(?:to\s+)?(.+)',
                comment,
                re.IGNORECASE
            )
            if match:
                field_type = match.group(1).lower()
                target_value = match.group(2).strip()
                
                field = "organisation" if field_type in ("organisation", "organization") else "dept" if field_type in ("dept", "department") else field_type
                
                # Check if database already matches the target value
                if doc.get(field) != target_value:
                    col.update_one(
                        {"_id": bid_no},
                        {"$set": {field: target_value}, "$unset": {"embedding": ""}}
                    )
                    logger.log_ok(f"Active Learning: Updated bid {bid_no} field {field} to '{target_value}' based on comment.")
                
                # Extract trigger phrase from comment
                phrase = None
                for line in comment.split("\n"):
                    line_clean = line.strip()
                    if "Sahkari Chini" in line_clean or "Mills Ltd" in line_clean or "Mill" in line_clean:
                        for kw in ["Sahkari Chini Mills Ltd.", "Sahkari Chini Mills Ltd", "Sahkari Chini Mills", "Kisan Sahkari Chini Mills"]:
                            if kw.lower() in line_clean.lower():
                                phrase = kw
                                break
                        if not phrase:
                            phrase = line_clean
                            phrase = re.sub(r'^[0-9\s,]+', '', phrase).strip()
                        break
                if not phrase:
                    phrase = dept or organisation or category
                
                if phrase:
                    # Add mapping rule if not present
                    exists = False
                    for rule in mappings:
                        if rule.get("field") == field and rule.get("phrase") == phrase and rule.get("key") == target_value:
                            exists = True
                            break
                    if not exists:
                        mappings.append({
                            "field": field,
                            "phrase": phrase,
                            "key": target_value
                        })
                        settings_changed = True
                        logger.log_ok(f"Active Learning: Extracted keyword mapping '{phrase}' -> '{target_value}' for field '{field}' from comments.")
                        
        if settings_changed:
            save_setting("value_mappings", mappings)
            
    except Exception as e:
        import logger
        logger.log_err(f"Active learning from comments failed: {e}")


def get_distinctive_keywords(s):
    import re
    if not s:
        return set()
    words = re.findall(r'\b[a-z]{4,}\b', s.lower())
    NOISE = {
        'ltd', 'limited', 'cooperative', 'sahkari', 'chini', 'mill', 'mills',
        'factory', 'corporation', 'state', 'unit', 'district', 'distt',
        'ganna', 'vikas', 'nigam', 'sahakari', 'sahakaree', 'cheeni', 'kissan',
        'kisan', 'operative', 'sugar', 'factories', 'federation', 'private',
        'pvt', 'gases', 'solutions', 'flux', 'weld', 'welding', 'alloys',
        'systems', 'technologies', 'india', 'officer', 'consignee', 'reporting',
        'address', 'delivery'
    }
    return {w for w in words if w not in NOISE}


def unify_value(val, existing_list):
    import difflib
    if not val or not str(val).strip():
        return val
        
    val_clean = str(val).strip()
    
    # 1. Direct close matches (high threshold)
    matches = difflib.get_close_matches(val_clean, existing_list, n=1, cutoff=0.75)
    if matches:
        return matches[0]
        
    # 2. Distinctive keyword overlap matching
    kw_val = get_distinctive_keywords(val_clean)
    if not kw_val:
        return val_clean
        
    best_match = None
    best_ratio = 0.0
    for exist_val in existing_list:
        kw_exist = get_distinctive_keywords(exist_val)
        if kw_val.intersection(kw_exist):
            ratio = difflib.SequenceMatcher(None, val_clean.lower(), exist_val.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = exist_val
                
    if best_match and best_ratio >= 0.4:
        return best_match
        
    return val_clean


def unify_organization_names(record: dict) -> dict:
    """
    Fuzzy standardizes organization, department, and ministry fields of the record
    against already existing entries in the database.
    """
    try:
        _, mdb = get_mongo_client()
        col = mdb["bids"]
        
        # Unify Ministry
        val_min = record.get("ministry")
        if val_min and str(val_min).strip():
            existing_mins = [m for m in col.distinct("ministry") if m and m != val_min]
            record["ministry"] = unify_value(val_min, existing_mins)
                
        # Unify Dept
        val_dept = record.get("dept")
        if val_dept and str(val_dept).strip():
            existing_depts = [d for d in col.distinct("dept") if d and d != val_dept]
            record["dept"] = unify_value(val_dept, existing_depts)

        # Unify Organisation
        val_org = record.get("organisation")
        if val_org and str(val_org).strip():
            existing_orgs = [o for o in col.distinct("organisation") if o and o != val_org]
            record["organisation"] = unify_value(val_org, existing_orgs)

        # Unify Location
        val_loc = record.get("location")
        if val_loc and str(val_loc).strip():
            existing_locs = [l for l in col.distinct("location") if l and l != val_loc]
            record["location"] = unify_value(val_loc, existing_locs)
    except Exception:
        pass
    return record


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
