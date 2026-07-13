import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'core'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'gui'))

import unittest
from app_gui import TenderApp

class TestFilterLogic(unittest.TestCase):
    def setUp(self):
        # We can construct a mock TenderApp or mock the _get_tender_status function
        # Since _get_tender_status is self-contained and takes (self, rec, inc_kws, exc_kws),
        # we can test it using a dummy self.
        self.app = object.__new__(TenderApp)
        from components.table_tab import TableTab
        self.app.table_tab = object.__new__(TableTab)
        self.app.table_tab.app = self.app
        from components.calendar_tab import CalendarTab
        self.app.calendar_tab = object.__new__(CalendarTab)
        self.app.calendar_tab.app = self.app
        import db
        self.old_settings = db.SETTINGS_FILE
        db.SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "test_filter_settings.json")
        if os.path.exists(db.SETTINGS_FILE):
            try: os.remove(db.SETTINGS_FILE)
            except: pass

    def tearDown(self):
        import db
        if os.path.exists(db.SETTINGS_FILE):
            try: os.remove(db.SETTINGS_FILE)
            except: pass
        db.SETTINGS_FILE = self.old_settings

    def test_filter_wants_empty_rules(self):
        # When rules are empty, all tenders should be Wants (True)
        rec = {"bid_no": "GEM/2026/B/1", "items": "Laptop Computer", "category": "IT"}
        res = self.app._get_tender_status(rec, [], [])
        self.assertTrue(res)

    def test_filter_include_keywords_as_safeguard(self):
        # Tenders not matching exclude keywords are considered wants
        rec1 = {"bid_no": "GEM/2026/B/1", "items": "Laptop Computer", "category": "IT"}
        
        # Tenders matching exclude keyword but also include keyword are considered wants (safeguard)
        rec2 = {"bid_no": "GEM/2026/B/2", "items": "Sugar Federation Mill", "category": "Sugar"}
        
        # Tenders matching exclude keyword but not include keyword are excluded
        rec3 = {"bid_no": "GEM/2026/B/3", "items": "Kisan Chini Mill", "category": "Sugar"}
        
        inc = ["federation", "laptop"]
        exc = ["mill"]
        
        # rec1: no exclude match -> True
        self.assertTrue(self.app._get_tender_status(rec1, inc, exc))
        # rec2: matches exclude ("mill") but also include ("federation") -> True
        self.assertTrue(self.app._get_tender_status(rec2, inc, exc))
        # rec3: matches exclude ("mill") but not include -> False
        self.assertFalse(self.app._get_tender_status(rec3, inc, exc))

    def test_filter_exclude_keywords(self):
        # Excludes matches containing exclude keywords
        rec1 = {"bid_no": "GEM/2026/B/1", "items": "Laptop Computer", "category": "IT"}
        rec2 = {"bid_no": "GEM/2026/B/2", "items": "Sugar Federation", "category": "Sugar"}
        
        inc = []
        exc = ["laptop", "computer"]
        
        self.assertFalse(self.app._get_tender_status(rec1, inc, exc))
        self.assertTrue(self.app._get_tender_status(rec2, inc, exc))

    def test_filter_manual_overrides(self):
        # Manual tagging overrides keyword filters
        rec = {
            "bid_no": "GEM/2026/B/1", 
            "items": "Laptop Computer", 
            "category": "IT",
            "is_want": False  # Manually marked as Don't Want
        }
        
        inc = ["laptop"] # matches include
        exc = []
        
        # Even though include matches, manual override is False
        self.assertFalse(self.app._get_tender_status(rec, inc, exc))

        rec2 = {
            "bid_no": "GEM/2026/B/2", 
            "items": "Sugar Transport", 
            "category": "Logistics",
            "is_want": True  # Manually marked as Want
        }
        inc = []
        exc = ["sugar"] # matches exclude
        
        # Even though exclude matches, manual override is True
        self.assertTrue(self.app._get_tender_status(rec2, inc, exc))

    def test_is_bid_in_dont_wants(self):
        # Setup mock records in app
        self.app._records = [
            {"bid_no": "GEM/2026/B/100", "bid_url": "https://bidplus.gem.gov.in/showbidDocument/100", "is_want": False}, # Don't want
            {"bid_no": "GEM/2026/B/200", "bid_url": "https://bidplus.gem.gov.in/showbidDocument/200", "is_want": True},  # Want
        ]
        
        # Test bid_no match
        self.assertTrue(self.app._is_bid_in_dont_wants("GEM/2026/B/100"))
        self.assertFalse(self.app._is_bid_in_dont_wants("GEM/2026/B/200"))
        
        # Test doc ID match (split "/")
        self.assertTrue(self.app._is_bid_in_dont_wants("100"))
        self.assertFalse(self.app._is_bid_in_dont_wants("200"))
        
        # Test non-existent
        self.assertFalse(self.app._is_bid_in_dont_wants("300"))

    def test_calendar_only_shows_wants(self):
        # Setup mock records in app
        self.app._records = [
            {"bid_no": "GEM/2026/B/100", "start_date": "01-07-2026", "is_want": False}, # Don't want
            {"bid_no": "GEM/2026/B/200", "start_date": "01-07-2026", "is_want": True},  # Want
        ]
        from datetime import date
        target = date(2026, 7, 1)
        events = self.app._get_events_for_date(target, [], [])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][1]["bid_no"], "GEM/2026/B/200")

    def test_table_view_date_filtering(self):
        from unittest.mock import MagicMock
        import tkinter as tk
        from components.table_view import TendersTableView
        
        root = MagicMock()
        self.app.table_tab.date_filter_type_var = MagicMock()
        self.app.table_tab.date_filter_type_var.get.return_value = "Start Date"
        self.app.table_tab.date_from_var = MagicMock()
        self.app.table_tab.date_from_var.get.return_value = "01-07-2026"
        self.app.table_tab.date_to_var = MagicMock()
        self.app.table_tab.date_to_var.get.return_value = "15-07-2026"
        self.app.table_tab.view_var = MagicMock()
        self.app.table_tab.view_var.get.return_value = "All Tenders"
        self.app.table_tab.search_var = MagicMock()
        self.app.table_tab.search_var.get.return_value = ""
        self.app.table_tab.semantic_search_var = MagicMock()
        self.app.table_tab.semantic_search_var.get.return_value = False
        self.app.table_tab.status_view_var = MagicMock()
        self.app.table_tab.status_view_var.get.return_value = "All"
        self.app.notebook = MagicMock()
        self.app.tab_calendar = MagicMock()
        self.app.tab_analytics = MagicMock()
        
        class DummyTreeview:
            def __init__(self):
                self.items = []
            def get_children(self):
                return list(self.items)
            def delete(self, item):
                self.items.remove(item)
            def insert(self, *args, **kwargs):
                self.items.append("dummy")
                return "dummy"
        
        self.app.table_tab.table_view = object.__new__(TendersTableView)
        self.app.table_tab.table_view.tv = DummyTreeview()
        self.app.table_tab.tv = self.app.table_tab.table_view.tv
        self.app.table_tab.count_lbl = MagicMock()
        self.app.table_tab.table_summary_lbl = MagicMock()
        self.app.table_tab.custom_date_frame = MagicMock()
        
        self.app.table_tab.table_view.tv_insert = lambda rec: self.app.table_tab.table_view.tv.insert()
        self.app.table_tab.table_view.refresh_alt = lambda: None
        
        # Keep references on app as well for backwards compatibility
        self.app.tv = self.app.table_tab.tv
        self.app.search_var = self.app.table_tab.search_var
        self.app.view_var = self.app.table_tab.view_var
        
        self.app._records = [
            {"bid_no": "GEM/2026/B/100", "start_date": "05-07-2026"}, 
            {"bid_no": "GEM/2026/B/200", "start_date": "20-07-2026"}, 
            {"bid_no": "GEM/2026/B/300", "start_date": "25-06-2026"}, 
        ]
        
        self.app._refresh_table_view()
        self.assertEqual(len(self.app.table_tab.table_view.tv.items), 1)
        root.destroy()

    def test_parse_date_str_robustness(self):
        from datetime import date
        # Test parsing DD-MM-YYYY / DD/MM/YYYY with 1 or 2 digits
        self.assertEqual(self.app._parse_date_str("01-07-2026"), date(2026, 7, 1))
        self.assertEqual(self.app._parse_date_str("1-7-2026"), date(2026, 7, 1))
        self.assertEqual(self.app._parse_date_str("01/07/2026"), date(2026, 7, 1))
        self.assertEqual(self.app._parse_date_str("1/7-2026"), date(2026, 7, 1)) # mixed separator
        
        # Test parsing YYYY-MM-DD / YYYY/MM/DD with 1 or 2 digits
        self.assertEqual(self.app._parse_date_str("2026-07-01"), date(2026, 7, 1))
        self.assertEqual(self.app._parse_date_str("2026/7/1"), date(2026, 7, 1))
        self.assertEqual(self.app._parse_date_str("2026-7-01"), date(2026, 7, 1))
        
        # Test invalid cases
        self.assertIsNone(self.app._parse_date_str("invalid"))
        self.assertIsNone(self.app._parse_date_str(None))

if __name__ == '__main__':
    unittest.main()
