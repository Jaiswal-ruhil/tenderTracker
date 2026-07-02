import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'core'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'gui'))

import unittest
import db

TEST_DB_FILE = os.path.join(os.path.dirname(__file__), "test_tenders_db.db")
TEST_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "temp_test_settings.json")

class TestDb(unittest.TestCase):
    def setUp(self):
        # Override the database file path and settings file to test files
        db.DB_FILE = TEST_DB_FILE
        db.SETTINGS_FILE = TEST_SETTINGS_FILE
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)
        if os.path.exists(TEST_SETTINGS_FILE):
            os.remove(TEST_SETTINGS_FILE)

    def tearDown(self):
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)
        if os.path.exists(TEST_SETTINGS_FILE):
            os.remove(TEST_SETTINGS_FILE)

    def test_settings_loading_saving(self):
        self.assertEqual(db.load_settings(), {})
        
        self.assertTrue(db.save_setting("excel_save_folder", "D:/exports"))
        self.assertEqual(db.load_settings().get("excel_save_folder"), "D:/exports")
        
        test_path = "D:/tenders/custom_tenders_db.db"
        self.assertTrue(db.save_configured_db_path(test_path))
        self.assertEqual(db.get_configured_db_path(), test_path)
        
        settings = db.load_settings()
        self.assertEqual(settings.get("excel_save_folder"), "D:/exports")
        self.assertEqual(settings.get("db_path"), test_path)
        
        self.assertTrue(db.save_setting("selenium_headless", True))
        self.assertTrue(db.save_setting("excel_filename_pattern", "Custom_Tenders_{fy}_{date}"))
        
        settings_new = db.load_settings()
        self.assertTrue(settings_new.get("selenium_headless"))
        self.assertEqual(settings_new.get("excel_filename_pattern"), "Custom_Tenders_{fy}_{date}")
        
        db.init_db_path()
        self.assertEqual(db.DB_FILE, test_path)
        
        os.remove(TEST_SETTINGS_FILE)
        db.init_db_path()
        self.assertEqual(db.DB_FILE, db.DEFAULT_DB_FILE)

    def test_load_save(self):
        # Initial load should be empty
        self.assertEqual(db.load_all_tenders(), [])
        
        # Save records
        records = [{"bid_no": "GEM/2026/B/1", "items": "Laptop"}]
        self.assertTrue(db.save_all_tenders(records))
        self.assertEqual(db.load_all_tenders(), records)

    def test_upsert_insert(self):
        record = {"bid_no": "GEM/2026/B/2", "items": "Monitor", "quantity": "10"}
        records = db.upsert_tender(record)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["bid_no"], "GEM/2026/B/2")
        self.assertEqual(records[0]["quantity"], "10")

    def test_upsert_merge(self):
        # Initial insert
        record1 = {"bid_no": "GEM/2026/B/3", "items": "Printer", "quantity": "5"}
        db.upsert_tender(record1)
        
        # Merge insert with extra details
        record2 = {"bid_no": "GEM/2026/B/3", "items": "Printer", "location": "New Delhi", "quantity": ""}
        records = db.upsert_tender(record2)
        
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["bid_no"], "GEM/2026/B/3")
        self.assertEqual(records[0]["quantity"], "5") # Preserved old value since new one is empty
        self.assertEqual(records[0]["location"], "New Delhi") # Merged new value

    def test_upsert_tenders_bulk(self):
        recs = [
            {"bid_no": "GEM/2026/B/4", "items": "Scanner"},
            {"bid_no": "GEM/2026/B/5", "items": "Projector"}
        ]
        records = db.upsert_tenders(recs)
        self.assertEqual(len(records), 2)
        
        # Test updating one and adding another
        recs_update = [
            {"bid_no": "GEM/2026/B/4", "location": "Mumbai"},
            {"bid_no": "GEM/2026/B/6", "items": "Camera"}
        ]
        records = db.upsert_tenders(recs_update)
        self.assertEqual(len(records), 3)
        
        scanner_rec = next(r for r in records if r["bid_no"] == "GEM/2026/B/4")
        self.assertEqual(scanner_rec["items"], "Scanner")
        self.assertEqual(scanner_rec["location"], "Mumbai")

    def test_delete_tenders(self):
        recs = [
            {"bid_no": "GEM/2026/B/7", "items": "Keyboard"},
            {"bid_no": "GEM/2026/B/8", "items": "Mouse"},
            {"bid_no": "GEM/2026/B/9", "items": "Desk"}
        ]
        db.upsert_tenders(recs)
        
        records = db.delete_tenders(["GEM/2026/B/7", "GEM/2026/B/9"])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["bid_no"], "GEM/2026/B/8")

    def test_corrupted_json(self):
        # Write corrupted invalid JSON to file
        with open(TEST_DB_FILE, "w", encoding="utf-8") as f:
            f.write("invalid json data {{{{")
        
        # Load should fail gracefully and return empty list
        self.assertEqual(db.load_all_tenders(), [])
        
        # Upsert should still succeed by writing fresh valid data
        record = {"bid_no": "GEM/2026/B/10", "items": "Chair"}
        records = db.upsert_tender(record)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["bid_no"], "GEM/2026/B/10")

    def test_concurrent_upserts(self):
        import threading
        
        num_threads = 8
        records_per_thread = 5
        threads = []
        
        def worker(thread_idx):
            for i in range(records_per_thread):
                bid_no = f"GEM/2026/B/THREAD-{thread_idx}-{i}"
                db.upsert_tender({"bid_no": bid_no, "items": f"Item {i}"})
                
        for t in range(num_threads):
            thread = threading.Thread(target=worker, args=(t,))
            threads.append(thread)
            thread.start()
            
        for thread in threads:
            thread.join()
            
        loaded = db.load_all_tenders()
        self.assertEqual(len(loaded), num_threads * records_per_thread)

    def test_fuzzy_unification(self):
        # Insert a base tender with specific ministry and department
        db.upsert_tender({
            "bid_no": "GEM/2026/B/BASE-1",
            "ministry": "Ministry of Jal Shakti",
            "dept": "Uttar Pradesh Cooperative Sugar Factories Federation Limited",
            "organisation": "Kisan Sahakari Chini Mill",
            "location": "Sathiaon - Kisan Sahkari Chini Mills Ltd. Sathiaon"
        })
        
        # Insert another tender with slight typos / variations
        db.upsert_tender({
            "bid_no": "GEM/2026/B/BASE-2",
            "ministry": "Ministry of Jall Shaktii", # 1 typo
            "dept": "Uttar Pradesh Coop Sugar Factories Federation Ltd", # Abbreviation
            "organisation": "Kisan Sahakaree Cheeni Mill", # Spelling difference
            "location": "Sathiaon - Kissan Sahkari Chini Mill Ltd. Sathiaon" # Slight spelling difference in location
        })

        # Insert a base tender with Mohiuddinpur location
        db.upsert_tender({
            "bid_no": "GEM/2026/B/BASE-3",
            "location": "Mohiuddinpur - UP State Sugar Corporation Limited Mohiuddinpur"
        })

        # Insert another tender with structural variation in Mohiuddinpur location
        db.upsert_tender({
            "bid_no": "GEM/2026/B/BASE-4",
            "location": "U.P.STATE SUGAR CORPORATION Ltd., unit Mohiuddinpur (Meerut) -250205"
        })
        
        # Load records and verify base-2 and base-4 got unified
        tenders = db.load_all_tenders()
        tenders_by_bid = {t["bid_no"]: t for t in tenders}
        
        base2 = tenders_by_bid["GEM/2026/B/BASE-2"]
        self.assertEqual(base2["ministry"], "Ministry of Jal Shakti")
        self.assertEqual(base2["dept"], "Uttar Pradesh Cooperative Sugar Factories Federation Limited")
        self.assertEqual(base2["organisation"], "Kisan Sahakari Chini Mill")
        self.assertEqual(base2["location"], "Sathiaon - Kisan Sahkari Chini Mills Ltd. Sathiaon")

        base4 = tenders_by_bid["GEM/2026/B/BASE-4"]
        self.assertEqual(base4["location"], "Mohiuddinpur - UP State Sugar Corporation Limited Mohiuddinpur")

if __name__ == '__main__':
    unittest.main()
