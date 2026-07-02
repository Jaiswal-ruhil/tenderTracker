import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'core'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'gui'))

import unittest
import db
import parser

TEST_DB_FILE = os.path.join(os.path.dirname(__file__), "test_tenders_db.db")
TEST_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "temp_test_settings_val.json")

class TestValueMappings(unittest.TestCase):
    def setUp(self):
        # Override the database file path and settings file to test files
        db.DB_FILE = TEST_DB_FILE
        db.SETTINGS_FILE = TEST_SETTINGS_FILE
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)
        if os.path.exists(TEST_SETTINGS_FILE):
            os.remove(TEST_SETTINGS_FILE)
            
        # Configure sample mappings
        self.sample_mappings = [
            {
                "field": "location",
                "key": "tilhar",
                "phrase": "24230,The Kisan Sahakari chini mill ltd TILHAR SHAHJAHANPUR GST NO\n09AAAAK0207C1ZD"
            },
            {
                "field": "location",
                "key": "najibabad",
                "phrase": "snehroad1990@gmail.com"
            },
            {
                "field": "category",
                "key": "ni screen",
                "phrase": "NK 1503 30 006mm 2 20 mm 0 27mm 6 to 4 Segment"
            }
        ]
        db.save_setting("value_mappings", self.sample_mappings)

    def tearDown(self):
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)
        if os.path.exists(TEST_SETTINGS_FILE):
            os.remove(TEST_SETTINGS_FILE)

    def test_apply_value_mappings_direct(self):
        # 1. Test Location mapping with tilhar
        rec1 = {
            "bid_no": "GEM/2026/B/001",
            "location": "24230,The Kisan Sahakari chini mill ltd TILHAR SHAHJAHANPUR GST NO\n09AAAAK0207C1ZD",
            "category": "Generic Category"
        }
        mapped1 = db.apply_value_mappings(rec1)
        self.assertEqual(mapped1["location"], "tilhar")
        self.assertEqual(mapped1["category"], "Generic Category")

        # 2. Test Location mapping with najibabad (case insensitivity)
        rec2 = {
            "bid_no": "GEM/2026/B/002",
            "location": "Contact at SnehRoad1990@gmail.com for details",
            "category": "Generic Category"
        }
        mapped2 = db.apply_value_mappings(rec2)
        self.assertEqual(mapped2["location"], "najibabad")

        # 3. Test Category mapping with spacing differences
        rec3 = {
            "bid_no": "GEM/2026/B/003",
            "location": "Somewhere",
            "category": "NK  1503  30  006mm  2  20  mm  0  27mm  6  to  4  Segment"
        }
        mapped3 = db.apply_value_mappings(rec3)
        self.assertEqual(mapped3["category"], "ni screen")

    def test_apply_value_mappings_no_match(self):
        rec = {
            "bid_no": "GEM/2026/B/004",
            "location": "Random Location, India",
            "category": "Other Category"
        }
        mapped = db.apply_value_mappings(rec)
        self.assertEqual(mapped["location"], "Random Location, India")
        self.assertEqual(mapped["category"], "Other Category")

    def test_upsert_integration(self):
        rec = {
            "bid_no": "GEM/2026/B/005",
            "location": "Contact us: snehroad1990@gmail.com",
            "category": "Other Category"
        }
        db.upsert_tender(rec)
        
        tenders = db.load_all_tenders()
        self.assertEqual(len(tenders), 1)
        self.assertEqual(tenders[0]["location"], "najibabad")

    def test_parser_integration(self):
        raw_text = """
BID NO: [GEM/2026/B/006](http://example.com)
Category: NK 1503 30 006mm 2 20 mm 0 27mm 6 to 4 Segment
Location: snehroad1990@gmail.com
"""
        parsed = parser.parse_one(raw_text)
        self.assertEqual(parsed["category"], "ni screen")
        self.assertEqual(parsed["location"], "najibabad")

if __name__ == '__main__':
    unittest.main()
