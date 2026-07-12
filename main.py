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