import os
import sys
import unittest
import tkinter as tk
from tkinter import ttk
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'core')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'gui')))

import app_gui


class TestUIPathTracker(unittest.TestCase):
    
    @classmethod
    @patch('app_gui.filedialog.askdirectory', return_value='d:/tenderTracker')
    @patch('app_gui.db.get_configured_db_path', return_value='d:/tenderTracker/tenders_db.db')
    def setUpClass(cls, mock_db_path, mock_ask):
        cls.root = app_gui.TenderApp()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def test_initial_path(self):
        self.assertEqual(self.root.ui_path_stack, ["UI/MAIN/TAB/TABLE"])
        self.assertIn("UI/MAIN/TAB/TABLE", self.root.ui_path_lbl.cget("text"))

    def test_push_pop_path(self):
        self.root.push_ui_path("TEST/PATH")
        self.assertEqual(self.root.ui_path_stack, ["UI/MAIN/TAB/TABLE", "TEST/PATH"])
        self.assertIn("UI/MAIN/TAB/TABLE ➔ TEST/PATH", self.root.ui_path_lbl.cget("text"))
        
        self.root.pop_ui_path()
        self.assertEqual(self.root.ui_path_stack, ["UI/MAIN/TAB/TABLE"])
        self.assertIn("UI/MAIN/TAB/TABLE", self.root.ui_path_lbl.cget("text"))

    def test_toplevel_auto_tracking(self):
        win = tk.Toplevel(self.root)
        self.assertIn("UI/DIALOG/TOPLEVEL", self.root.ui_path_stack[-1])
        
        win.title("My Special Dialog")
        self.assertEqual(self.root.ui_path_stack[-1], "UI/DIALOG/MY_SPECIAL_DIALOG")
        
        win.destroy()
        self.root.update()
        self.assertEqual(self.root.ui_path_stack, ["UI/MAIN/TAB/TABLE"])

    def test_widget_path_resolution(self):
        # 1. Test button path
        btn = tk.Button(self.root, text="Start Filing")
        path = self.root._resolve_widget_path(btn)
        self.assertEqual(path, "BTN/START_FILING")
        
        # 2. Test entry path
        entry = tk.Entry(self.root, name="search_field")
        path = self.root._resolve_widget_path(entry)
        self.assertEqual(path, "INPUT/SEARCH_FIELD")
        
        # 3. Test label path
        lbl = tk.Label(self.root, text="Bid Number:")
        path = self.root._resolve_widget_path(lbl)
        self.assertEqual(path, "LBL/BID_NUMBER")
        
        # 4. Test nested hierarchy
        parent_frame = tk.Frame(self.root, name="table_frame")
        child_btn = tk.Button(parent_frame, text="Submit")
        path = self.root._resolve_widget_path(child_btn)
        self.assertEqual(path, "TABLE_FRAME/BTN/SUBMIT")
        
        # 5. Test string widget path resolution (simulating event.widget as a string)
        string_path = self.root._resolve_widget_path(str(child_btn))
        self.assertEqual(string_path, "TABLE_FRAME/BTN/SUBMIT")
