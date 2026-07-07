import logging
import os
import queue
import time
import threading

log_queue = queue.Queue()
_file_handler = None

# ── Freeze Watchdog ───────────────────────────────────────────────────────────
# Monitors the Tkinter main thread via a shared heartbeat timestamp.
# If the main thread doesn't update the heartbeat within the threshold,
# it logs a warning/error with the freeze duration.

_heartbeat_time = time.monotonic()
_heartbeat_lock = threading.Lock()
_watchdog_running = False

FREEZE_WARN_MS   = 1000   # warn if UI unresponsive > 1s
FREEZE_CRIT_MS   = 3000   # escalate to error if > 3s
WATCHDOG_INTERVAL = 0.5   # check every 500ms

def update_heartbeat():
    """Call this from the Tkinter main-thread poll loop (_poll_log_queue)."""
    global _heartbeat_time
    with _heartbeat_lock:
        _heartbeat_time = time.monotonic()

def _watchdog_loop():
    last_warned = 0.0
    last_check_time = time.monotonic()
    while _watchdog_running:
        time.sleep(WATCHDOG_INTERVAL)
        if not _watchdog_running:
            break
        
        now = time.monotonic()
        sleep_elapsed = now - last_check_time
        last_check_time = now
        
        # If the sleep call took significantly longer than normal (e.g., >3s),
        # the computer went to sleep/suspended. Reset heartbeat and skip logging.
        if sleep_elapsed > WATCHDOG_INTERVAL + 2.5:
            with _heartbeat_lock:
                global _heartbeat_time
                _heartbeat_time = now
            continue

        with _heartbeat_lock:
            elapsed_ms = (now - _heartbeat_time) * 1000

        if elapsed_ms >= FREEZE_CRIT_MS:
            if now - last_warned > 2.0:
                log("err", f"UI FREEZE: Main thread unresponsive for {elapsed_ms:.0f}ms")
                last_warned = now
        elif elapsed_ms >= FREEZE_WARN_MS:
            if now - last_warned > 2.0:
                log("warn", f"UI SLOW: Main thread delayed {elapsed_ms:.0f}ms")
                last_warned = now

def start_watchdog():
    """Start the UI freeze watchdog. Call once after app startup."""
    global _watchdog_running
    if _watchdog_running:
        return
    _watchdog_running = True
    t = threading.Thread(target=_watchdog_loop, daemon=True, name="UIFreezeWatchdog")
    t.start()

def stop_watchdog():
    global _watchdog_running
    _watchdog_running = False

# ── Timer helper ──────────────────────────────────────────────────────────────
def elapsed_since(start: float) -> str:
    """Human-readable elapsed time from a monotonic start timestamp."""
    ms = (time.monotonic() - start) * 1000
    return f"{ms:.0f}ms" if ms < 1000 else f"{ms/1000:.2f}s"

# ── File logger setup ─────────────────────────────────────────────────────────
def get_log_file_path(db_path):
    """Derive log file path from database path."""
    if db_path.lower().endswith(".db"):
        return db_path[:-3] + ".log"
    return db_path + ".log"

def setup_file_logger(db_path):
    """Set up or reconfigure the file handler targeting the database folder."""
    global _file_handler
    log_path = get_log_file_path(db_path)
    root_logger = logging.getLogger()
    if _file_handler:
        root_logger.removeHandler(_file_handler)
        _file_handler.close()
    try:
        parent_dir = os.path.dirname(os.path.abspath(log_path))
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        _file_handler = logging.FileHandler(log_path, encoding="utf-8")
        _file_handler.setFormatter(logging.Formatter(
            "[%(asctime)s] %(levelname)-7s %(message)s", datefmt="%H:%M:%S"
        ))
        _file_handler.setLevel(logging.DEBUG)
        root_logger.addHandler(_file_handler)
        log("info", f"Log file: {log_path}")
    except Exception as e:
        print(f"Failed to setup file logger at {log_path}: {e}")

class SafeStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            super().emit(record)
        except Exception:
            pass

    def flush(self):
        try:
            super().flush()
        except Exception:
            pass

# Base logger configuration
logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[SafeStreamHandler()]
)


# ── Core log function ─────────────────────────────────────────────────────────
def log(level, message, details=None):
    """
    Log a message with a specific UI level (info, ok, warn, err).
    Writes to the file logger and queues for the GUI log panel.
    """
    if level == "ok":
        logging.info(f"[OK]   {message}")
    elif level == "warn":
        logging.warning(f"[WARN] {message}")
    elif level == "err":
        logging.error(f"[ERR]  {message}")
    else:
        logging.info(f"[INFO] {message}")
    log_queue.put((level, message, details))

def log_info(msg, details=None): log("info", msg, details)
def log_ok(msg, details=None):   log("ok",   msg, details)
def log_warn(msg, details=None): log("warn", msg, details)
def log_err(msg, details=None):  log("err",  msg, details)

# ── Structured UI event helpers ───────────────────────────────────────────────
def log_button_click(label: str):
    """Log a button press from the UI."""
    log("info", f"[BTN]  '{label}' clicked")

def log_tab_change(tab_name: str):
    """Log a notebook tab transition."""
    log("info", f"[TAB]  → {tab_name}")

def log_worker_start(name: str) -> float:
    """Log background worker start; returns a monotonic start timestamp."""
    log("info", f"[WORK] ▶ {name} started")
    return time.monotonic()

def log_worker_done(name: str, start: float):
    """Log background worker completion with elapsed time."""
    log("ok", f"[WORK] ✓ {name} finished in {elapsed_since(start)}")

def log_worker_error(name: str, start: float, error):
    """Log background worker failure with elapsed time."""
    log("err", f"[WORK] ✗ {name} failed after {elapsed_since(start)}: {error}")
