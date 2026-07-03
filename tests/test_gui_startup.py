import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'core'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'gui'))

import unittest
from unittest.mock import patch
import tkinter as tk
import db
from app_gui import TenderApp

class TestGuiStartup(unittest.TestCase):
    def setUp(self):
        self.old_db = db.DB_FILE
        self.old_settings = db.SETTINGS_FILE
        db.DB_FILE = os.path.join(os.path.dirname(__file__), "test_gui_tenders_db.db")
        db.SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "test_gui_settings.json")
        if os.path.exists(db.DB_FILE):
            try: os.remove(db.DB_FILE)
            except: pass
        if os.path.exists(db.SETTINGS_FILE):
            try: os.remove(db.SETTINGS_FILE)
            except: pass

    def tearDown(self):
        if os.path.exists(db.DB_FILE):
            try: os.remove(db.DB_FILE)
            except: pass
        if os.path.exists(db.SETTINGS_FILE):
            try: os.remove(db.SETTINGS_FILE)
            except: pass
        db.DB_FILE = self.old_db
        db.SETTINGS_FILE = self.old_settings

    @patch('tkinter.filedialog.askdirectory')
    @patch('db.get_configured_db_path')
    def test_gui_open_close(self, mock_get_cfg, mock_askdir):
        """
        Instantiates TenderApp, updates its layout, and verifies it closes cleanly without crashing.
        """
        # Configure mocks to return test path and bypass UI dialog popup
        mock_get_cfg.return_value = db.DB_FILE
        mock_askdir.return_value = os.path.dirname(db.DB_FILE)
        
        try:
            app = TenderApp()
            # Run idle tasks to build and layout all widgets
            app.update_idletasks()
            
            # Schedule self-destruction after 100ms
            app.after(100, app.destroy)
            
            # Run event loop
            app.mainloop()
            
            # If we reach here, startup and teardown were successful
            self.assertTrue(True)
        except tk.TclError as e:
            # Some test environments lack a usable Tcl/Tk installation; skip in that case.
            self.skipTest(f"Tcl/Tk not available in test environment: {e}")
        except Exception as e:
            self.fail(f"TenderApp failed to open/close cleanly: {e}")

if __name__ == '__main__':
    unittest.main()
