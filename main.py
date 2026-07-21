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

# ─── MongoDB connectivity & container auto-start check ───────────────────────
# db.py is now a pure MongoDB shim — no SQLite fallback.
# If MongoDB is unreachable, attempt to start the container automatically.
# ──────────────────────────────────────────────────────────────────────────────
import db  # noqa: E402  (path must be set first)

if not db.is_mongo_available():
    # Show a loading splash window while starting Docker / MongoDB
    splash = tk.Tk()
    splash.title("TenderTracker")
    splash.geometry("420x150")
    splash.resizable(False, False)
    splash.configure(bg="#f8f9fa")

    try:
        splash.eval('tk::PlaceWindow . center')
    except Exception:
        pass

    lbl_title = tk.Label(
        splash,
        text="Starting MongoDB Container...",
        font=("Segoe UI", 11, "bold"),
        bg="#f8f9fa",
        fg="#1a1a1a"
    )
    lbl_title.pack(pady=(25, 5))

    lbl_status = tk.Label(
        splash,
        text="Launching Docker & initializing database...",
        font=("Segoe UI", 9),
        bg="#f8f9fa",
        fg="#555555"
    )
    lbl_status.pack(pady=5)

    success_holder = [False]

    def start_bg():
        def update_status(text):
            def _ui():
                try:
                    lbl_status.config(text=text)
                except Exception:
                    pass
            splash.after(0, _ui)

        success_holder[0] = db.ensure_mongo_container_running(status_callback=update_status)
        splash.after(0, splash.destroy)

    import threading
    t = threading.Thread(target=start_bg, daemon=True)
    t.start()
    splash.mainloop()

    if not success_holder[0]:
        _root = tk.Tk()
        _root.withdraw()
        messagebox.showerror(
            "MongoDB Not Available",
            "TenderTracker requires MongoDB (Docker).\n\n"
            "Could not automatically start the MongoDB container.\n"
            "Please ensure Docker Desktop is running and try:\n\n"
            "    docker compose up -d\n\n"
            "Then relaunch the application.",
        )
        _root.destroy()
        sys.exit(1)

print("[TenderTracker] MongoDB backend active.")

from app_gui import TenderApp  # noqa: E402

if __name__ == "__main__":
    # Enable high-DPI awareness on Windows for a crisp, high-resolution UI
    try:
        import ctypes
        # 2 = PROCESS_PER_MONITOR_DPI_AWARE_V2 (Windows 10 1703+)
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            import ctypes
            # 1 = PROCESS_SYSTEM_DPI_AWARE
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                import ctypes
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    app = TenderApp()
    app.mainloop()