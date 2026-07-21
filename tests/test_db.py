import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'core'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'gui'))

import unittest
import db

# conftest.py resets mongo_db to a fresh mongomock instance before every test.
# No SQLite file overrides needed.

class TestDb(unittest.TestCase):

    def test_settings_loading_saving(self):
        self.assertEqual(db.load_settings(), {})

        self.assertTrue(db.save_setting("excel_save_folder", "D:/exports"))
        self.assertEqual(db.load_settings().get("excel_save_folder"), "D:/exports")

        self.assertTrue(db.save_setting("selenium_headless", True))
        self.assertTrue(db.save_setting("excel_filename_pattern", "Custom_Tenders_{fy}_{date}"))

        settings_new = db.load_settings()
        self.assertTrue(settings_new.get("selenium_headless"))
        self.assertEqual(settings_new.get("excel_filename_pattern"), "Custom_Tenders_{fy}_{date}")

    def test_configured_db_path(self):
        # save_configured_db_path / get_configured_db_path are stubs that store
        # the value in the MongoDB settings collection.
        test_path = "D:/tenders/custom_tenders_db.db"
        self.assertTrue(db.save_configured_db_path(test_path))
        self.assertEqual(db.get_configured_db_path(), test_path)

    def test_load_save(self):
        self.assertEqual(db.load_all_tenders(), [])

        records = [{"bid_no": "GEM/2026/B/1", "items": "Laptop"}]
        self.assertTrue(db.save_all_tenders(records))
        loaded = db.load_all_tenders()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["bid_no"], "GEM/2026/B/1")

    def test_upsert_insert(self):
        record = {"bid_no": "GEM/2026/B/2", "items": "Monitor", "quantity": "10"}
        records = db.upsert_tender(record)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["bid_no"], "GEM/2026/B/2")
        self.assertEqual(records[0]["quantity"], "10")

    def test_upsert_merge(self):
        record1 = {"bid_no": "GEM/2026/B/3", "items": "Printer", "quantity": "5"}
        db.upsert_tender(record1)

        record2 = {"bid_no": "GEM/2026/B/3", "items": "Printer", "location": "New Delhi", "quantity": ""}
        records = db.upsert_tender(record2)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["bid_no"], "GEM/2026/B/3")
        self.assertEqual(records[0]["quantity"], "5")          # old value preserved (new is empty)
        self.assertEqual(records[0]["location"], "New Delhi")  # new value merged

    def test_upsert_tenders_bulk(self):
        recs = [
            {"bid_no": "GEM/2026/B/4", "items": "Scanner"},
            {"bid_no": "GEM/2026/B/5", "items": "Projector"},
        ]
        records = db.upsert_tenders(recs)
        self.assertEqual(len(records), 2)

        recs_update = [
            {"bid_no": "GEM/2026/B/4", "location": "Mumbai"},
            {"bid_no": "GEM/2026/B/6", "items": "Camera"},
        ]
        records = db.upsert_tenders(recs_update)
        self.assertEqual(len(records), 3)

        scanner_rec = next(r for r in records if r["bid_no"] == "GEM/2026/B/4")
        self.assertEqual(scanner_rec["items"], "Scanner")
        self.assertEqual(scanner_rec["location"], "Mumbai")

    def test_ingest_tenders_batch(self):
        batch_recs = [
            {"bid_no": f"GEM/2026/B/BATCH-{i}", "items": f"Item {i}", "category": "General"}
            for i in range(10)
        ]
        result = db.ingest_tenders_batch(batch_recs, batch_size=3)
        self.assertEqual(result["total"], 10)
        self.assertGreaterEqual(result["processed"], 10)

        all_tenders = db.load_all_tenders()
        batch_bids = [t for t in all_tenders if "BATCH" in t["bid_no"]]
        self.assertEqual(len(batch_bids), 10)

    def test_delete_tenders(self):
        recs = [
            {"bid_no": "GEM/2026/B/7", "items": "Keyboard"},
            {"bid_no": "GEM/2026/B/8", "items": "Mouse"},
            {"bid_no": "GEM/2026/B/9", "items": "Desk"},
        ]
        db.upsert_tenders(recs)

        records = db.delete_tenders(["GEM/2026/B/7", "GEM/2026/B/9"])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["bid_no"], "GEM/2026/B/8")

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
        db.upsert_tender({
            "bid_no": "GEM/2026/B/BASE-1",
            "ministry": "Ministry of Jal Shakti",
            "dept": "Uttar Pradesh Cooperative Sugar Factories Federation Limited",
            "organisation": "Kisan Sahakari Chini Mill",
            "location": "Sathiaon - Kisan Sahkari Chini Mills Ltd. Sathiaon",
        })

        db.upsert_tender({
            "bid_no": "GEM/2026/B/BASE-2",
            "ministry": "Ministry of Jall Shaktii",
            "dept": "Uttar Pradesh Coop Sugar Factories Federation Ltd",
            "organisation": "Kisan Sahakaree Cheeni Mill",
            "location": "Sathiaon - Kissan Sahkari Chini Mill Ltd. Sathiaon",
        })

        db.upsert_tender({
            "bid_no": "GEM/2026/B/BASE-3",
            "location": "Mohiuddinpur - UP State Sugar Corporation Limited Mohiuddinpur",
        })

        db.upsert_tender({
            "bid_no": "GEM/2026/B/BASE-4",
            "location": "U.P.STATE SUGAR CORPORATION Ltd., unit Mohiuddinpur (Meerut) -250205",
        })

        tenders = db.load_all_tenders()
        tenders_by_bid = {t["bid_no"]: t for t in tenders}

        base2 = tenders_by_bid["GEM/2026/B/BASE-2"]
        self.assertEqual(base2["ministry"], "Ministry of Jal Shakti")
        self.assertEqual(base2["dept"], "Uttar Pradesh Cooperative Sugar Factories Federation Limited")
        self.assertEqual(base2["organisation"], "Kisan Sahakari Chini Mill")

        base4 = tenders_by_bid["GEM/2026/B/BASE-4"]
        self.assertEqual(base4["location"], "Mohiuddinpur - UP State Sugar Corporation Limited Mohiuddinpur")

    def test_bid_result_and_competitors(self):
        db.upsert_tender({"bid_no": "GEM/2026/B/RES-1", "items": "Cable"})

        result = {
            "result": "Lost",
            "our_rank": 2,
            "our_price": 500000.0,
            "l1_price": 450000.0,
            "price_gap": 50000.0,
            "price_gap_pct": 11.11,
            "notes": "L1 was cheaper due to MSE benefit",
            "recorded_at": "2026-07-16T18:00:00",
        }
        self.assertTrue(db.save_bid_result("GEM/2026/B/RES-1", result))
        fetched = db.get_bid_result("GEM/2026/B/RES-1")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["result"], "Lost")
        self.assertAlmostEqual(fetched["price_gap_pct"], 11.11, places=1)

        competitors = [
            {"rank": 1, "seller_name": "Acme Ltd", "total_price": 450000.0, "is_own_bid": False},
            {"rank": 2, "seller_name": "Our Firm", "total_price": 500000.0, "is_own_bid": True},
        ]
        self.assertTrue(db.save_bid_competitors("GEM/2026/B/RES-1", competitors))
        fetched_comps = db.get_bid_competitors("GEM/2026/B/RES-1")
        self.assertEqual(len(fetched_comps), 2)
        self.assertEqual(fetched_comps[0]["rank"], 1)

    def test_extra_fields(self):
        db.upsert_tender({"bid_no": "GEM/2026/B/EX-1", "items": "Motor"})
        db.set_extra_field("GEM/2026/B/EX-1", "warranty_years", "3")
        extras = db.get_extra_fields("GEM/2026/B/EX-1")
        self.assertEqual(extras.get("warranty_years"), "3")

    def test_text_search(self):
        db.upsert_tender({"bid_no": "GEM/2026/B/SRC-1", "items": "Diesel Generator Set 500KVA"})
        db.upsert_tender({"bid_no": "GEM/2026/B/SRC-2", "items": "LED Street Light 150W"})
        results = db.text_search_tenders("Generator", limit=10)
        bid_nos = [r["bid_no"] for r in results]
        self.assertIn("GEM/2026/B/SRC-1", bid_nos)
        self.assertNotIn("GEM/2026/B/SRC-2", bid_nos)


if __name__ == '__main__':
    unittest.main()
