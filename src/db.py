import os
import json
import threading

SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".tendertracker_settings.json")
DEFAULT_DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tenders_db.json")
DB_FILE = DEFAULT_DB_FILE
_lock = threading.RLock()

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
        return DB_FILE
    cfg_path = get_configured_db_path()
    if cfg_path:
        DB_FILE = cfg_path
    else:
        DB_FILE = DEFAULT_DB_FILE
    return DB_FILE

def load_all_tenders():
    """Load all tenders from the local JSON file. Thread-safe."""
    with _lock:
        if not os.path.exists(DB_FILE):
            return []
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

def save_all_tenders(records):
    """Save all tenders to the local JSON file. Thread-safe."""
    with _lock:
        try:
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=4, ensure_ascii=False)
            return True
        except Exception:
            return False

def upsert_tender(record):
    """Insert or update a tender record. Thread-safe."""
    with _lock:
        records = load_all_tenders()
        bid_no = record.get("bid_no")
        if not bid_no:
            return records
            
        found = False
        for existing in records:
            if existing.get("bid_no") == bid_no:
                # Merge new fields into the existing record
                for k, v in record.items():
                    if v is not None and str(v).strip() != "":
                        if k not in existing or not str(existing[k]).strip() or k in ("is_saved", "is_fetched"):
                            existing[k] = v
                found = True
                break
        
        if not found:
            records.append(record)
            
        save_all_tenders(records)
        return records

def upsert_tenders(new_records):
    """Bulk insert or update tender records. Thread-safe."""
    with _lock:
        records = load_all_tenders()
        for new_rec in new_records:
            bid_no = new_rec.get("bid_no")
            if not bid_no:
                continue
            found = False
            for existing in records:
                if existing.get("bid_no") == bid_no:
                    # Merge new fields into the existing record
                    for k, v in new_rec.items():
                        if v is not None and str(v).strip() != "":
                            if k not in existing or not str(existing[k]).strip() or k in ("is_saved", "is_fetched"):
                                existing[k] = v
                    found = True
                    break
            if not found:
                records.append(new_rec)
        save_all_tenders(records)
        return records

def delete_tenders(bid_numbers):
    """Delete tenders by their bid numbers. Thread-safe."""
    with _lock:
        records = load_all_tenders()
        filtered = [r for r in records if r.get("bid_no") not in bid_numbers]
        save_all_tenders(filtered)
        return filtered
