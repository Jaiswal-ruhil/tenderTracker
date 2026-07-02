import logging
import os
import queue

log_queue = queue.Queue()
_file_handler = None

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
    
    # Remove existing file handler if any
    if _file_handler:
        root_logger.removeHandler(_file_handler)
        _file_handler.close()
        
    try:
        # Create parent directory if it doesn't exist
        parent_dir = os.path.dirname(os.path.abspath(log_path))
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
            
        _file_handler = logging.FileHandler(log_path, encoding='utf-8')
        _file_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%H:%M:%S'))
        _file_handler.setLevel(logging.INFO)
        root_logger.addHandler(_file_handler)
    except Exception as e:
        print(f"Failed to setup file logger at {log_path}: {e}")

# Base logger configuration
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.StreamHandler()] # Print to stdout/stderr by default
)

def log(level, message):
    """
    Log a message with a specific UI level (info, ok, warn, err).
    Saves to the file logger and sends to the UI queue.
    """
    # Map level to standard logging
    if level == "ok":
        logging.info(message)
    elif level == "warn":
        logging.warning(message)
    elif level == "err":
        logging.error(message)
    else:
        logging.info(message)
        
    # Queue for GUI main thread consumption
    log_queue.put((level, message))

def log_info(msg):
    log("info", msg)

def log_ok(msg):
    log("ok", msg)

def log_warn(msg):
    log("warn", msg)

def log_err(msg):
    log("err", msg)
