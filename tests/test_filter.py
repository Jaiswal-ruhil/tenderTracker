import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import unittest
from gui import TenderApp

class TestFilterLogic(unittest.TestCase):
    def setUp(self):
        # We can construct a mock TenderApp or mock the _get_tender_status function
        # Since _get_tender_status is self-contained and takes (self, rec, inc_kws, exc_kws),
        # we can test it using a dummy self.
        self.app = object.__new__(TenderApp)

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

if __name__ == '__main__':
    unittest.main()
