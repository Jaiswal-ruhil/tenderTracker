import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure src paths are in sys.path
_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, os.path.join(_ROOT, "src", "core"))
sys.path.insert(0, os.path.join(_ROOT, "src", "gui"))
sys.path.insert(0, os.path.join(_ROOT, "src", "core", "parsers"))
sys.path.insert(0, os.path.join(_ROOT, "src", "core", "ai"))
sys.path.insert(0, os.path.join(_ROOT, "src", "core", "workflow"))

from config import TV_IDS
import workers


class MockTableView:
    def _compute_closing_in(self, end_date):
        if not end_date:
            return "", None
        return "5d 4h", "warn_dl"


class MockTableTab:
    def __init__(self):
        self.table_view = MockTableView()


class MockTreeview:
    def __init__(self):
        self.items = {}
        self.item_tags = {}
        self.counter = 0

    def get_children(self):
        return list(self.items.keys())

    def set(self, iid, col, val=None):
        if val is None:
            return self.items.get(iid, {}).get(col, "")
        if iid not in self.items:
            self.items[iid] = {}
        self.items[iid][col] = str(val)
        return val

    def item(self, iid, option=None, tags=None):
        if tags is not None:
            self.item_tags[iid] = tags
        return {"tags": self.item_tags.get(iid, ())}

    def insert(self, parent, index, values=None, tags=None):
        self.counter += 1
        iid = f"item_{self.counter}"
        self.items[iid] = {}
        if values:
            for idx, col in enumerate(TV_IDS):
                if idx < len(values):
                    self.items[iid][col] = str(values[idx])
        if tags:
            self.item_tags[iid] = tags
        return iid


class DummyApp(workers.WorkersMixin):
    def __init__(self):
        self.tv = MockTreeview()
        self.table_tab = MockTableTab()
        self._records = []
        self.logs = []

    def _log(self, level, msg, details=None):
        self.logs.append((level, msg))

    def _tv_insert(self, rec):
        raw_vals = []
        for c in TV_IDS:
            if c == "closing_in":
                ci, _ = self.table_tab.table_view._compute_closing_in(rec.get("end_date", ""))
                raw_vals.append(ci)
            else:
                val = rec.get(c, "")
                if c == "tags" and isinstance(val, list):
                    val = ", ".join(val)
                raw_vals.append(val)
        return self.tv.insert("", "end", values=tuple(raw_vals), tags=("fetched",))

    def _get_tender_status(self, rec, inc_kws, exc_kws, settings=None):
        return True

    def _show_toast(self, title, msg, level="info"):
        pass


class TestWorkersMixin(unittest.TestCase):
    def setUp(self):
        self.app = DummyApp()

    def test_block_dedupe_key(self):
        self.assertEqual(workers._block_dedupe_key("GEM/2026/B/7711387"), "GEM/2026/B/7711387")
        self.assertEqual(workers._block_dedupe_key("showbidDocument/7711387"), "7711387")
        self.assertEqual(workers._block_dedupe_key("   \"GEM/2026/B/7711387\"  "), "GEM/2026/B/7711387")

    def test_parse_item_timeout(self):
        settings_llm = {"llm_provider": "Local LLM", "llm_use_parsing": True}
        settings_disabled = {"llm_provider": "Disabled", "llm_use_parsing": False}

        self.assertEqual(workers._parse_item_timeout("sample.pdf", settings_disabled), 60.0)
        self.assertEqual(workers._parse_item_timeout("some text block", settings_llm), 180.0)
        self.assertEqual(workers._parse_item_timeout("GEM/2026/B/7711387", settings_disabled), 120.0)
        self.assertEqual(workers._parse_item_timeout("short block", settings_disabled), 45.0)

    def test_format_eta(self):
        self.assertEqual(workers._format_eta(0), "0s left")
        self.assertEqual(workers._format_eta(45), "~45s left")
        self.assertEqual(workers._format_eta(125), "~2m 5s left")

    def test_add_rows_batch_populates_all_columns(self):
        parsed_recs = [
            {
                "bid_no": "GEM/2026/B/7732857",
                "category": "Motor",
                "dept": "Ministry of Mines",
                "items": "High Efficiency Electric Motor 50HP",
                "quantity": "5",
                "location": "Lucknow 226001",
                "est_value": "500000",
                "eval_method": "Total value wise",
                "bid_type": "Two Packet",
                "emd": "Yes",
                "epbg": "No",
                "mii": "Yes",
                "min_turnover": "10 Lakh",
                "exp_years": "3 Years",
                "end_date": "2026-08-01 15:00:00",
                "start_date": "2026-07-20",
                "matched_firm": "RK ELECTRODES",
                "remarks": "Parsed successfully via PDF LLM"
            }
        ]
        stats = {"added": 0, "updated": 0}
        self.app._add_rows_batch(parsed_recs, stats)

        self.assertEqual(stats["added"], 1)
        self.assertEqual(len(self.app._records), 1)
        iid = self.app.tv.get_children()[0]
        self.assertEqual(self.app.tv.set(iid, "bid_no"), "GEM/2026/B/7732857")
        self.assertEqual(self.app.tv.set(iid, "category"), "Motor")
        self.assertEqual(self.app.tv.set(iid, "dept"), "Ministry of Mines")
        self.assertEqual(self.app.tv.set(iid, "items"), "High Efficiency Electric Motor 50HP")
        self.assertEqual(self.app.tv.set(iid, "quantity"), "5")
        self.assertEqual(self.app.tv.set(iid, "closing_in"), "5d 4h")
        self.assertEqual(self.app.tv.set(iid, "matched_firm"), "RK ELECTRODES")

    def test_add_rows_batch_updates_existing_row(self):
        # Insert initial partial record
        initial_rec = {
            "bid_no": "GEM/2026/B/9999999",
            "items": "Initial Item Name",
        }
        stats = {"added": 0, "updated": 0}
        self.app._add_rows_batch([initial_rec], stats)

        iid = self.app.tv.get_children()[0]
        self.assertEqual(self.app.tv.set(iid, "category"), "")

        # Now parse PDF and receive rich updated fields
        llm_extracted_rec = {
            "bid_no": "GEM/2026/B/9999999",
            "category": "Industrial Oxygen Cylinder",
            "dept": "Health Department UP",
            "items": "Industrial Oxygen Cylinder 47L",
            "quantity": "20",
            "end_date": "2026-08-10 14:00:00",
            "matched_firm": "Firm ABC",
        }
        self.app._add_rows_batch([llm_extracted_rec], stats)

        self.assertEqual(stats["updated"], 1)
        self.assertEqual(self.app.tv.set(iid, "category"), "Industrial Oxygen Cylinder")
        self.assertEqual(self.app.tv.set(iid, "dept"), "Health Department UP")
        self.assertEqual(self.app.tv.set(iid, "closing_in"), "5d 4h")
        self.assertEqual(self.app.tv.set(iid, "matched_firm"), "Firm ABC")

    def test_add_single_row_immediate(self):
        rec = {
            "bid_no": "GEM/2026/B/1112223",
            "category": "Cable",
            "items": "Armoured Power Cable 4 Core",
            "end_date": "2026-08-15",
        }
        stats = {"added": 0, "updated": 0}
        self.app._add_single_row_immediate(rec, stats)

        self.assertEqual(stats["added"], 1)
        iid = self.app.tv.get_children()[0]
        self.assertEqual(self.app.tv.set(iid, "category"), "Cable")
        self.assertEqual(self.app.tv.set(iid, "closing_in"), "5d 4h")


if __name__ == "__main__":
    unittest.main()
