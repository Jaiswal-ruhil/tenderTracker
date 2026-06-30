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

    def test_filter_include_keywords(self):
        # Only matches containing include keywords
        rec1 = {"bid_no": "GEM/2026/B/1", "items": "Laptop Computer", "category": "IT"}
        rec2 = {"bid_no": "GEM/2026/B/2", "items": "Sugar Federation", "category": "Sugar"}
        
        inc = ["sugar", "transport"]
        exc = []
        
        self.assertFalse(self.app._get_tender_status(rec1, inc, exc))
        self.assertTrue(self.app._get_tender_status(rec2, inc, exc))

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

if __name__ == '__main__':
    unittest.main()
