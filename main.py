"""
GEM Tender Logger — Desktop UI Launcher (v4)
--------------------------------------
This file serves as the main entry point to run the GEM Tender Logger application.
The application has been modularized into config, parser, scraper, excel, and gui modules.

Requirements:
    pip install openpyxl selenium webdriver-manager
    Google Chrome must be installed

Run:
    python main.py
"""

import os
import sys

# Ensure src and its subdirectories are in python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'core'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'gui'))

# ─── MongoDB Backend Injection ──────────────────────────────────────────────────
# If MongoDB (Docker) is reachable, register mongo_db as the 'db' module
# so every `import db` anywhere in the codebase gets MongoDB functions.
# Falls back to SQLite silently if Docker is not running.
# To force SQLite: set TENDERTRACKER_USE_SQLITE=1 in environment.
# ─────────────────────────────────────────────────────────────────────────────
if not os.environ.get('TENDERTRACKER_USE_SQLITE'):
    try:
        import mongo_db as _mongo_db_mod
        if _mongo_db_mod.is_mongo_available():
            sys.modules['db'] = _mongo_db_mod
            print("[TenderTracker] MongoDB backend active (docker compose up -d)")
        else:
            print("[TenderTracker] MongoDB not reachable — using SQLite. Start with: docker compose up -d")
    except Exception as _e:
        print(f"[TenderTracker] MongoDB unavailable ({_e}) — using SQLite.")

from app_gui import TenderApp

if __name__ == "__main__":
    # Enable high-DPI awareness on Windows for a crisper UI and more screen real estate
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    app = TenderApp()
    app.mainloop()