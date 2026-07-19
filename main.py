"""
GEM Tender Logger — Desktop UI Launcher (v4)
--------------------------------------------
MongoDB (Docker) is the only supported data backend.

Start MongoDB:
    docker compose up -d

Run the app:
    python main.py
"""

import os
import sys
import tkinter as tk
from tkinter import messagebox

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'core'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'gui'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'core', 'parsers'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'core', 'ai'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'core', 'workflow'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'mcp'))

# ─── MongoDB connectivity check ────────────────────────────────────────────────
# db.py is now a pure MongoDB shim — no SQLite fallback.
# If MongoDB is unreachable we show an error dialog and exit cleanly.
# ──────────────────────────────────────────────────────────────────────────────
import db  # noqa: E402  (path must be set first)

if not db.is_mongo_available():
    _root = tk.Tk()
    _root.withdraw()
    messagebox.showerror(
        "MongoDB Not Available",
        "TenderTracker requires MongoDB (Docker).\n\n"
        "Start the container and try again:\n\n"
        "    docker compose up -d\n\n"
        "Then relaunch the application.",
    )
    _root.destroy()
    sys.exit(1)

print("[TenderTracker] MongoDB backend active.")

from app_gui import TenderApp  # noqa: E402

if __name__ == "__main__":
    # Enable high-DPI awareness on Windows for a crisper UI
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