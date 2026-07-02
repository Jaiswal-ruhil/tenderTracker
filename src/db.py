import os
import json
import sqlite3
import threading
import logger

SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".tendertracker_settings.json")
DEFAULT_DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tenders_db.db")
DB_FILE = DEFAULT_DB_FILE
_lock = threading.RLock()

# Settings loading/saving functions (keeps JSON settings file)
def load_settings():
    """Load all settings from the settings file."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_setting(key, value):
    """Save a single setting key-value pair to the settings file."""
    try:
        settings = load_settings()
        settings[key] = value
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)
        return True
    except Exception:
        return False

def get_configured_db_path():
    """Load configured DB path from settings file."""
    return load_settings().get("db_path")

def save_configured_db_path(path):
    """Save configured DB path to settings file."""
    return save_setting("db_path", path)

def init_db_path(custom_path=None):
    """Initialize DB_FILE path using custom path, settings file, or default path."""
    global DB_FILE
    if custom_path:
        DB_FILE = custom_path
    else:
        cfg_path = get_configured_db_path()
        if cfg_path:
            DB_FILE = cfg_path
        else:
            DB_FILE = DEFAULT_DB_FILE
    
    # Run migration check for either the custom or default DB path
    resolved_db = get_resolved_db_path()
    legacy_json = None
    if DB_FILE.lower().endswith(".json"):
        legacy_json = DB_FILE
    elif DB_FILE.lower().endswith(".db"):
        legacy_json = DB_FILE[:-3] + ".json"
        
    if legacy_json and os.path.exists(legacy_json) and not os.path.exists(resolved_db):
        migrate_json_to_sqlite(legacy_json, resolved_db)
        
    # Force DB_FILE to be the resolved SQLite .db database path
    DB_FILE = resolved_db
    
    # Update the settings file if it was still configured to point to the legacy .json
    cfg_path = get_configured_db_path()
    if cfg_path and cfg_path.lower().endswith(".json"):
        save_configured_db_path(DB_FILE)
        
    return DB_FILE

def migrate_json_to_sqlite(json_path, sqlite_path):
    """Migrates legacy JSON tenders database to SQLite."""
    try:
        logger.log_info(f"Starting legacy database migration from {os.path.basename(json_path)} to SQLite...")
        with open(json_path, "r", encoding="utf-8") as f:
            records = json.load(f)
        if records:
            # Temporarily set DB_FILE to sqlite_path to call save_all_tenders
            global DB_FILE
            old_db_file = DB_FILE
            DB_FILE = sqlite_path
            init_db_connection()
            save_all_tenders(records)
            DB_FILE = old_db_file
        backup_path = json_path + ".bak"
        if os.path.exists(backup_path):
            os.remove(backup_path)
        os.rename(json_path, backup_path)
        logger.log_ok("Migration from legacy JSON database completed successfully.")
    except Exception as e:
        logger.log_err(f"Failed to migrate legacy JSON database: {e}")

# SQLite Helpers
def get_resolved_db_path():
    db_path = DB_FILE
    if db_path.lower().endswith(".json"):
        db_path = db_path[:-5] + ".db"
    return db_path

def get_conn():
    db_path = get_resolved_db_path()
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tenders'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE tenders (
                    bid_no TEXT PRIMARY KEY,
                    bid_url TEXT,
                    ministry TEXT,
                    dept TEXT,
                    organisation TEXT,
                    office TEXT,
                    category TEXT,
                    items TEXT,
                    quantity TEXT,
                    location TEXT,
                    contract_dur TEXT,
                    est_value TEXT,
                    eval_method TEXT,
                    bid_type TEXT,
                    bid_to_ra TEXT,
                    emd TEXT,
                    epbg TEXT,
                    mii TEXT,
                    mse_pref TEXT,
                    mse_relax TEXT,
                    startup_relax TEXT,
                    min_turnover TEXT,
                    exp_years TEXT,
                    bid_opening TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    is_want INTEGER,
                    is_want_derived INTEGER,
                    is_saved INTEGER,
                    is_fetched INTEGER,
                    filing_status TEXT,
                    remarks TEXT,
                    tags TEXT
                )
            """)
            conn.commit()
        else:
            # Check for and dynamically add missing columns
            cursor.execute("PRAGMA table_info(tenders)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            for col in COLUMNS:
                if col not in existing_cols:
                    col_type = "INTEGER" if col in ("is_want", "is_want_derived", "is_saved", "is_fetched") else "TEXT"
                    cursor.execute(f"ALTER TABLE tenders ADD COLUMN {col} {col_type}")
            conn.commit()
    except Exception as e:
        try: conn.close()
        except Exception: pass
        raise e
    return conn

def init_db_connection():
    """Create the table if it does not exist."""
    with _lock:
        try:
            conn = get_conn()
            conn.close()
        except Exception:
            pass

def handle_db_error(e):
    err_msg = str(e).lower()
    if "is not a database" in err_msg or "malformed" in err_msg:
        with _lock:
            try:
                db_path = get_resolved_db_path()
                os.remove(db_path)
                init_db_connection()
            except Exception:
                pass

# List of columns to map database rows to dicts
COLUMNS = [
    "bid_no", "bid_url", "ministry", "dept", "organisation", "office", "category",
    "items", "quantity", "location", "contract_dur", "est_value", "eval_method",
    "bid_type", "bid_to_ra", "emd", "epbg", "mii", "mse_pref", "mse_relax",
    "startup_relax", "min_turnover", "exp_years", "bid_opening", "start_date", "end_date",
    "is_want", "is_want_derived", "is_saved", "is_fetched", "filing_status", "remarks", "tags"
]

def row_to_dict(row):
    d = {}
    for i, col in enumerate(COLUMNS):
        val = row[i]
        # Deserialize tag list and boolean values
        if col == "tags":
            try:
                tags_list = json.loads(val) if val else []
                if tags_list:
                    d[col] = tags_list
            except Exception:
                pass
        elif col in ("is_want", "is_want_derived", "is_saved", "is_fetched"):
            if val is not None:
                d[col] = bool(val)
        else:
            if val is not None and str(val).strip() != "":
                d[col] = val
    # bid_no is required
    if "bid_no" not in d:
        d["bid_no"] = ""
    return d

def dict_to_row(d):
    vals = []
    for col in COLUMNS:
        val = d.get(col)
        if col == "tags":
            vals.append(json.dumps(val) if val else "[]")
        elif col in ("is_want", "is_want_derived", "is_saved", "is_fetched"):
            if val is None:
                vals.append(None)
            else:
                vals.append(1 if val else 0)
        else:
            vals.append(str(val) if val is not None else "")
    return tuple(vals)

def load_all_tenders():
    """Load all tenders from SQLite. Thread-safe."""
    with _lock:
        conn = None
        try:
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tenders")
            rows = cursor.fetchall()
            return [row_to_dict(r) for r in rows]
        except sqlite3.DatabaseError as e:
            handle_db_error(e)
            return []
        except Exception:
            return []
        finally:
            if conn:
                try: conn.close()
                except Exception: pass

def save_all_tenders(records):
    """Save all tenders to SQLite (replaces all existing). Thread-safe."""
    with _lock:
        def do_save():
            conn = get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM tenders")
                placeholders = ",".join(["?"] * len(COLUMNS))
                sql = f"INSERT OR REPLACE INTO tenders VALUES ({placeholders})"
                rows = [dict_to_row(r) for r in records]
                cursor.executemany(sql, rows)
                conn.commit()
            finally:
                conn.close()

        try:
            do_save()
            return True
        except sqlite3.DatabaseError as e:
            handle_db_error(e)
            try:
                do_save()
                return True
            except Exception as ex:
                logger.log_err(f"Database write error: {ex}")
                return False
        except Exception as e:
            logger.log_err(f"Database write error: {e}")
            return False

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

def unify_organization_names(record, cursor=None):
    """
    Fuzzy standardizes organization, department, and ministry fields of the record
    against already existing entries in the database.
    """
    close_conn = False
    if cursor is None:
        try:
            conn = get_conn()
            cursor = conn.cursor()
            close_conn = True
        except Exception:
            return record
            
    try:
        # Unify Ministry
        val_min = record.get("ministry")
        if val_min and str(val_min).strip():
            cursor.execute("SELECT DISTINCT ministry FROM tenders WHERE ministry IS NOT NULL AND ministry != ''")
            existing_mins = [r[0] for r in cursor.fetchall() if r[0] != val_min]
            record["ministry"] = unify_value(val_min, existing_mins)
                
        # Unify Dept
        val_dept = record.get("dept")
        if val_dept and str(val_dept).strip():
            cursor.execute("SELECT DISTINCT dept FROM tenders WHERE dept IS NOT NULL AND dept != ''")
            existing_depts = [r[0] for r in cursor.fetchall() if r[0] != val_dept]
            record["dept"] = unify_value(val_dept, existing_depts)

        # Unify Organisation
        val_org = record.get("organisation")
        if val_org and str(val_org).strip():
            cursor.execute("SELECT DISTINCT organisation FROM tenders WHERE organisation IS NOT NULL AND organisation != ''")
            existing_orgs = [r[0] for r in cursor.fetchall() if r[0] != val_org]
            record["organisation"] = unify_value(val_org, existing_orgs)

        # Unify Location
        val_loc = record.get("location")
        if val_loc and str(val_loc).strip():
            cursor.execute("SELECT DISTINCT location FROM tenders WHERE location IS NOT NULL AND location != ''")
            existing_locs = [r[0] for r in cursor.fetchall() if r[0] != val_loc]
            record["location"] = unify_value(val_loc, existing_locs)
    except Exception:
        pass
    finally:
        if close_conn and cursor:
            try:
                cursor.connection.close()
            except Exception:
                pass
                
    return record

def apply_value_mappings(record):
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

def upsert_tender(record):
    """Insert or update a single tender record. Thread-safe."""
    with _lock:
        bid_no = record.get("bid_no")
        if not bid_no:
            return load_all_tenders()
            
        record = apply_value_mappings(record)
        # Unify organization names before upserting
        record = unify_organization_names(record)
            
        def do_upsert():
            conn = get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM tenders WHERE bid_no=?", (bid_no,))
                row = cursor.fetchone()
                
                if row:
                    existing = row_to_dict(row)
                    for k, v in record.items():
                        if v is not None and str(v).strip() != "":
                            if k not in existing or not str(existing[k]).strip() or k in ("is_saved", "is_fetched", "is_want", "tags"):
                                existing[k] = v
                    row_data = dict_to_row(existing)
                else:
                    row_data = dict_to_row(record)
                    
                placeholders = ",".join(["?"] * len(COLUMNS))
                cursor.execute(f"INSERT OR REPLACE INTO tenders VALUES ({placeholders})", row_data)
                conn.commit()
            finally:
                conn.close()

        try:
            do_upsert()
        except sqlite3.DatabaseError as e:
            handle_db_error(e)
            try:
                do_upsert()
            except Exception:
                pass
        except Exception:
            pass
        return load_all_tenders()

def upsert_tenders(new_records):
    """Bulk insert or update tender records. Thread-safe."""
    with _lock:
        def do_bulk_upsert():
            conn = get_conn()
            try:
                cursor = conn.cursor()
                for record in new_records:
                    bid_no = record.get("bid_no")
                    if not bid_no:
                        continue
                        
                    record = apply_value_mappings(record)
                    # Unify organization names using existing cursor
                    record = unify_organization_names(record, cursor)
                    
                    cursor.execute("SELECT * FROM tenders WHERE bid_no=?", (bid_no,))
                    row = cursor.fetchone()
                    
                    if row:
                        existing = row_to_dict(row)
                        for k, v in record.items():
                            if v is not None and str(v).strip() != "":
                                if k not in existing or not str(existing[k]).strip() or k in ("is_saved", "is_fetched", "is_want", "tags"):
                                    existing[k] = v
                        row_data = dict_to_row(existing)
                    else:
                        row_data = dict_to_row(record)
                        
                    placeholders = ",".join(["?"] * len(COLUMNS))
                    cursor.execute(f"INSERT OR REPLACE INTO tenders VALUES ({placeholders})", row_data)
                conn.commit()
            finally:
                conn.close()

        try:
            do_bulk_upsert()
        except sqlite3.DatabaseError as e:
            handle_db_error(e)
            try:
                do_bulk_upsert()
            except Exception:
                pass
        except Exception:
            pass
        return load_all_tenders()

def delete_tenders(bid_numbers):
    """Delete tenders by their bid numbers. Thread-safe."""
    with _lock:
        conn = None
        try:
            conn = get_conn()
            cursor = conn.cursor()
            for bid in bid_numbers:
                cursor.execute("DELETE FROM tenders WHERE bid_no=?", (bid,))
            conn.commit()
        except Exception:
            pass
        finally:
            if conn:
                try: conn.close()
                except Exception: pass
        return load_all_tenders()

def upsert_tender_field(bid_no, field, value):
    """
    Surgically update a single field for a tender.
    Unlike upsert_tender(), this ALWAYS overwrites the existing value —
    intended for explicit user edits (category, filing_status, remarks, tags).
    Thread-safe.
    """
    if field not in COLUMNS:
        logger.log_err(f"upsert_tender_field: unknown field '{field}'")
        return False
    with _lock:
        conn = None
        try:
            conn = get_conn()
            cursor = conn.cursor()
            if field == "tags":
                db_val = json.dumps(value) if value else "[]"
            elif field in ("is_want", "is_want_derived", "is_saved", "is_fetched"):
                db_val = 1 if value else 0
            else:
                db_val = str(value) if value is not None else ""
            cursor.execute(
                f"UPDATE tenders SET {field}=? WHERE bid_no=?",
                (db_val, bid_no)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.log_err(f"upsert_tender_field error for {bid_no}.{field}: {e}")
            return False
        finally:
            if conn:
                try: conn.close()
                except Exception: pass
