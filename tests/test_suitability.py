import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'core'))

import db
import suitability

class TestSuitability(unittest.TestCase):
    def setUp(self):
        # Isolation is handled by conftest.py (mongomock fresh instance per test)
        db.init_db_connection()

    def tearDown(self):
        pass

    def test_default_profile(self):
        profile = db.get_company_profile()
        self.assertEqual(profile["categories"], [])
        self.assertFalse(profile["is_mse"])
        self.assertEqual(profile["max_emd"], -1)

    def test_save_and_get_profile(self):
        custom = {
            "categories": ["Motor", "Cable"],
            "max_est_value": 500000,
            "min_exp_years": 3,
            "min_turnover": 1000000,
            "location_keywords": ["UP"],
            "is_mse": True,
            "is_startup": False,
            "max_emd": 10000
        }
        db.save_company_profile(custom)
        profile = db.get_company_profile()
        self.assertEqual(profile["max_est_value"], 500000)
        self.assertEqual(profile["categories"], ["Motor", "Cable"])
        self.assertTrue(profile["is_mse"])

    @patch('llm.call_llm')
    def test_evaluate_suitability_success(self, mock_call_llm):
        # Configure LLM settings
        db.save_setting("llm_provider", "Google AI Studio (Gemini)")
        db.save_setting("llm_api_key", "mock_key")
        
        # Mock LLM response
        mock_call_llm.return_value = '{"suitable": true, "reasoning": "Fits all criteria perfectly."}'
        
        # Insert a mock tender
        record = {
            "bid_no": "GEM/2026/B/11111",
            "items": "5HP Electric Motor",
            "category": "Motor",
            "est_value": "150000",
            "emd": "No",
            "location": "Lucknow, UP"
        }
        db.upsert_tender(record)
        
        profile = db.get_company_profile()
        res = suitability.evaluate_tender_suitability(record, profile)
        
        self.assertTrue(res["success"])
        self.assertTrue(res["suitable"])
        self.assertIn("Fits all criteria", res["reasoning"])
        
        # Load from DB and verify updates
        tenders = db.load_all_tenders()
        tenders_map = {t["bid_no"]: t for t in tenders}
        self.assertTrue(tenders_map["GEM/2026/B/11111"]["is_want_derived"])
        self.assertIn("AI Suitability: SUITABLE", tenders_map["GEM/2026/B/11111"]["remarks"])

    def test_evaluate_suitability_disabled_provider(self):
        db.save_setting("llm_provider", "Disabled")
        record = {"bid_no": "GEM/2026/B/22222"}
        profile = db.get_company_profile()
        res = suitability.evaluate_tender_suitability(record, profile)
        self.assertFalse(res["success"])
        self.assertIn("disabled", res["error"])

if __name__ == '__main__':
    unittest.main()
