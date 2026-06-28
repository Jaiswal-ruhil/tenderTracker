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

from gui import TenderApp

if __name__ == "__main__":
    app = TenderApp()
    app.mainloop()