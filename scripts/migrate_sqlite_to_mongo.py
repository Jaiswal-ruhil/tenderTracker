#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migrate_sqlite_to_mongo.py
--------------------------
One-shot migration of all TenderTracker SQLite data into MongoDB.

Usage:
    python scripts/migrate_sqlite_to_mongo.py
    python scripts/migrate_sqlite_to_mongo.py --sqlite-path D:\\custom\\tenders_db.db
    python scripts/migrate_sqlite_to_mongo.py --dry-run

Prerequisites:
    - Docker MongoDB container running:  docker compose up -d
    - pymongo installed:                 pip install pymongo
"""

import argparse
import json
import os
import sqlite3
import sys

# ── path setup ────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR   = os.path.dirname(SCRIPT_DIR)
SRC_CORE   = os.path.join(ROOT_DIR, "src", "core")
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, SRC_CORE)

# ── defaults ──────────────────────────────────────────────────────────────────
DEFAULT_SQLITE_PATH   = os.path.join(ROOT_DIR, "tenders_db.db")
DEFAULT_SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".tendertracker_settings.json")
MONGO_URI             = "mongodb://localhost:27017/"
MONGO_DB_NAME         = "tendertracker"


def _get_mongo_db(uri: str, db_name: str):
    try:
        from pymongo import MongoClient
    except ImportError:
        print("[ERROR] pymongo not installed.  Run: pip install pymongo")
        sys.exit(1)
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
    except Exception as e:
        print(f"[ERROR] Cannot reach MongoDB at {uri}: {e}")
        print("        Start Docker container with:  docker compose up -d")
        sys.exit(1)
    return client[db_name]


def _sqlite_conn(path: str):
    if not os.path.exists(path):
        print(f"[ERROR] SQLite file not found: {path}")
        sys.exit(1)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


# ── per-table helpers ─────────────────────────────────────────────────────────

def _row_to_dict(row) -> dict:
    return {k: row[k] for k in row.keys()}


def migrate_bids(sqlite_path: str, mdb, dry_run: bool) -> int:
    print("\n── Migrating bids ──────────────────────────────────────────────")
    conn = _sqlite_conn(sqlite_path)
    try:
        rows = conn.execute("SELECT * FROM bids").fetchall()
    except Exception as e:
        print(f"   [SKIP] bids table not found or unreadable: {e}")
        return 0
    finally:
        conn.close()

    col = mdb["bids"]
    inserted = updated = skipped = 0

    for row in rows:
        d = _row_to_dict(row)
        bid_no = d.get("bid_no")
        if not bid_no:
            skipped += 1
            continue

        # Deserialize JSON-encoded list fields stored as strings in SQLite
        for field in ("tags",):
            if isinstance(d.get(field), str):
                try:
                    d[field] = json.loads(d[field])
                except Exception:
                    d[field] = []

        # Convert integer booleans to Python bool
        for field in ("is_want",):
            if isinstance(d.get(field), int):
                d[field] = bool(d[field])

        d["_id"] = bid_no

        if dry_run:
            inserted += 1
            continue

        existing = col.find_one({"_id": bid_no})
        if existing:
            # Merge: update non-empty fields without overwriting Filed status
            update_fields = {}
            for k, v in d.items():
                if v is None or (isinstance(v, str) and not v.strip()):
                    continue
                if k == "filing_status" and existing.get("filing_status") == "Filed":
                    continue
                update_fields[k] = v
            if update_fields:
                col.update_one({"_id": bid_no}, {"$set": update_fields})
                updated += 1
        else:
            col.insert_one(d)
            inserted += 1

    print(f"   Bids: {len(rows)} rows → inserted {inserted}, updated {updated}, skipped {skipped}")
    return inserted + updated


def migrate_classifications(sqlite_path: str, mdb, dry_run: bool) -> int:
    print("\n── Migrating classifications ────────────────────────────────────")
    conn = _sqlite_conn(sqlite_path)
    try:
        rows = conn.execute("SELECT * FROM classifications").fetchall()
    except Exception as e:
        print(f"   [SKIP] classifications table not found: {e}")
        return 0
    finally:
        conn.close()

    col = mdb["classifications"]
    count = 0
    for row in rows:
        d = _row_to_dict(row)
        bid_no = d.get("bid_no")
        if not bid_no:
            continue
        d["_id"] = bid_no
        if not dry_run:
            col.replace_one({"_id": bid_no}, d, upsert=True)
        count += 1

    print(f"   Classifications: {count} rows migrated")
    return count


def migrate_cache(sqlite_path: str, mdb, dry_run: bool) -> int:
    print("\n── Migrating LLM classification cache ──────────────────────────")
    conn = _sqlite_conn(sqlite_path)
    try:
        rows = conn.execute("SELECT * FROM llm_classifications").fetchall()
    except Exception:
        try:
            rows = conn.execute("SELECT * FROM cache").fetchall()
        except Exception as e:
            print(f"   [SKIP] cache/llm_classifications table not found: {e}")
            return 0
    finally:
        conn.close()

    col = mdb["cache"]
    count = 0
    for row in rows:
        d = _row_to_dict(row)
        cache_key = d.get("cache_key") or d.get("_id")
        if not cache_key:
            continue
        value = d.get("value") or d.get("result") or d
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except Exception:
                pass
        if not dry_run:
            col.update_one(
                {"_id": cache_key},
                {"$set": {"value": value}},
                upsert=True,
            )
        count += 1

    print(f"   Cache: {count} rows migrated")
    return count


def migrate_bid_results(sqlite_path: str, mdb, dry_run: bool) -> int:
    print("\n── Migrating bid results ────────────────────────────────────────")
    conn = _sqlite_conn(sqlite_path)
    try:
        rows = conn.execute("SELECT * FROM bid_results").fetchall()
    except Exception as e:
        print(f"   [SKIP] bid_results table not found: {e}")
        return 0
    finally:
        conn.close()

    bids_col = mdb["bids"]
    count = 0
    for row in rows:
        d = _row_to_dict(row)
        bid_no = d.pop("bid_no", None)
        if not bid_no:
            continue
        if not dry_run:
            bids_col.update_one(
                {"_id": bid_no},
                {"$set": {"bid_result": d}},
                upsert=False,
            )
        count += 1

    print(f"   Bid results: {count} rows migrated (embedded in bids documents)")
    return count


def migrate_bid_competitors(sqlite_path: str, mdb, dry_run: bool) -> int:
    print("\n── Migrating bid competitors ─────────────────────────────────────")
    conn = _sqlite_conn(sqlite_path)
    try:
        rows = conn.execute("SELECT * FROM bid_competitors").fetchall()
    except Exception as e:
        print(f"   [SKIP] bid_competitors table not found: {e}")
        return 0
    finally:
        conn.close()

    bids_col = mdb["bids"]
    # Group by bid_no
    by_bid: dict = {}
    for row in rows:
        d = _row_to_dict(row)
        bid_no = d.pop("bid_no", None)
        d.pop("id", None)
        if bid_no:
            by_bid.setdefault(bid_no, []).append(d)

    count = 0
    for bid_no, competitors in by_bid.items():
        if not dry_run:
            bids_col.update_one(
                {"_id": bid_no},
                {"$set": {"competitors": competitors}},
                upsert=False,
            )
        count += len(competitors)

    print(f"   Competitors: {count} rows migrated across {len(by_bid)} bids")
    return count


def migrate_settings(settings_file: str, mdb, dry_run: bool) -> int:
    print("\n── Migrating settings (JSON file) ──────────────────────────────")
    if not os.path.exists(settings_file):
        print(f"   [SKIP] Settings file not found: {settings_file}")
        return 0

    try:
        with open(settings_file, "r", encoding="utf-8") as f:
            settings = json.load(f)
    except Exception as e:
        print(f"   [SKIP] Failed to read settings file: {e}")
        return 0

    if not dry_run:
        mdb["settings"].update_one(
            {"_id": "global"},
            {"$set": {"data": settings}},
            upsert=True,
        )

    key_count = len(settings)
    print(f"   Settings: {key_count} keys migrated")
    return key_count


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Migrate TenderTracker SQLite data to MongoDB"
    )
    parser.add_argument(
        "--sqlite-path",
        default=DEFAULT_SQLITE_PATH,
        help=f"Path to SQLite .db file (default: {DEFAULT_SQLITE_PATH})",
    )
    parser.add_argument(
        "--settings-file",
        default=DEFAULT_SETTINGS_FILE,
        help=f"Path to settings JSON file (default: {DEFAULT_SETTINGS_FILE})",
    )
    parser.add_argument(
        "--mongo-uri",
        default=MONGO_URI,
        help=f"MongoDB connection URI (default: {MONGO_URI})",
    )
    parser.add_argument(
        "--mongo-db",
        default=MONGO_DB_NAME,
        help=f"MongoDB database name (default: {MONGO_DB_NAME})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count rows to migrate without writing to MongoDB",
    )
    args = parser.parse_args()

    print("=" * 60)
    print(" TenderTracker: SQLite → MongoDB Migration")
    print("=" * 60)
    print(f" SQLite   : {args.sqlite_path}")
    print(f" Settings : {args.settings_file}")
    print(f" MongoDB  : {args.mongo_uri}{args.mongo_db}")
    if args.dry_run:
        print(" Mode     : DRY RUN (no writes)")
    print("=" * 60)

    mdb = _get_mongo_db(args.mongo_uri, args.mongo_db)

    total = 0
    total += migrate_bids(args.sqlite_path, mdb, args.dry_run)
    total += migrate_classifications(args.sqlite_path, mdb, args.dry_run)
    total += migrate_cache(args.sqlite_path, mdb, args.dry_run)
    total += migrate_bid_results(args.sqlite_path, mdb, args.dry_run)
    total += migrate_bid_competitors(args.sqlite_path, mdb, args.dry_run)
    total += migrate_settings(args.settings_file, mdb, args.dry_run)

    print("\n" + "=" * 60)
    if args.dry_run:
        print(f" DRY RUN complete — {total} records would be migrated.")
    else:
        print(f" Migration complete — {total} records written to MongoDB.")
        print(f" Launch the app:  python main.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
