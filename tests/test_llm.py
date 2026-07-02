import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import llm
import parser
import db

class TestLLM(unittest.TestCase):
    def setUp(self):
        # Save old DB/settings paths to restore after tests
        self.old_db = db.DB_FILE
        self.old_settings = db.SETTINGS_FILE
        db.DB_FILE = os.path.join(os.path.dirname(__file__), "test_llm_tenders_db.db")
        db.SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "test_llm_settings.json")
        
        # Clear any existing test settings/db files
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

    def test_clean_json_response(self):
        # Test cleaning clean JSON
        self.assertEqual(llm.clean_json_response('{"test": 1}'), '{"test": 1}')
        
        # Test cleaning JSON in markdown code blocks
        self.assertEqual(llm.clean_json_response('```json\n{"test": 2}\n```'), '{"test": 2}')
        self.assertEqual(llm.clean_json_response('```\n{"test": 3}\n```'), '{"test": 3}')
        
        # Test cleaning JSON with leading/trailing text
        self.assertEqual(llm.clean_json_response('Here is the data:\n{"test": 4}\nHope this helps!'), '{"test": 4}')

    @patch('urllib.request.urlopen')
    def test_test_llm_connection_gemini_success(self, mock_urlopen):
        # Mock Gemini response
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"candidates": [{"content": {"parts": [{"text": "OK"}]}}]}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        success, msg = llm.test_llm_connection("Google AI Studio (Gemini)", "test_key", "", "gemini-1.5-flash")
        self.assertTrue(success)
        self.assertEqual(msg, "Connection successful.")

    @patch('urllib.request.urlopen')
    def test_test_llm_connection_local_success(self, mock_urlopen):
        # Mock LM Studio response
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"choices": [{"message": {"content": "ok"}}]}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        success, msg = llm.test_llm_connection("Local LLM (LM Studio / Ollama)", "", "http://localhost:1234/v1", "local-model")
        self.assertTrue(success)
        self.assertEqual(msg, "Connection successful.")

    @patch('urllib.request.urlopen')
    def test_test_llm_connection_failure(self, mock_urlopen):
        # Mock request exception
        mock_urlopen.side_effect = Exception("Connection refused")

        success, msg = llm.test_llm_connection("Local LLM (LM Studio / Ollama)", "", "http://localhost:1234/v1", "local-model")
        self.assertFalse(success)
        self.assertIn("Connection refused", msg)

    @patch('llm.call_llm')
    def test_llm_parse_tender(self, mock_call_llm):
        mock_call_llm.return_value = """
        {
            "bid_no": "GEM/2026/B/7711387",
            "bid_url": "https://bidplus.gem.gov.in/showbidDocument/7711387",
            "ministry": "Uttar Pradesh",
            "dept": "Cooperative Sugar Factories Federation",
            "organisation": "N/A",
            "office": "Lucknow",
            "category": "Industrial Gas",
            "items": "Refilling of Gases",
            "quantity": "500",
            "location": "Lucknow, UP",
            "contract_dur": "1 Year",
            "est_value": "100000",
            "eval_method": "Item-wise",
            "bid_type": "Two Packet",
            "bid_to_ra": "No",
            "emd": "No",
            "epbg": "No",
            "mii": "Yes",
            "mse_pref": "Yes",
            "mse_relax": "No",
            "startup_relax": "No",
            "min_turnover": "N/A",
            "exp_years": "2",
            "bid_opening": "06-07-2026 15:30:00",
            "start_date": "25-06-2026",
            "end_date": "06-07-2026 15:00:00"
        }
        """
        res = llm.llm_parse_tender("Raw block text", "Google AI Studio (Gemini)", "key", "", "model")
        self.assertEqual(res["bid_no"], "GEM/2026/B/7711387")
        self.assertEqual(res["category"], "Industrial Gas")
        self.assertEqual(res["quantity"], "500")

    @patch('llm.call_llm')
    def test_llm_map_category(self, mock_call_llm):
        mock_call_llm.return_value = '{"category": "Motor"}'
        res = llm.llm_map_category("5HP pump motor", ["Motor", "Cable"], "Google AI Studio (Gemini)", "key", "", "model")
        self.assertEqual(res, "Motor")

    @patch('llm.llm_parse_tender')
    def test_parser_parse_one_with_llm(self, mock_llm_parse):
        # Enable LLM parsing in settings
        db.save_setting("llm_provider", "Google AI Studio (Gemini)")
        db.save_setting("llm_api_key", "test_key")
        db.save_setting("llm_use_parsing", True)

        mock_llm_parse.return_value = {
            "bid_no": "GEM/2026/B/12345",
            "bid_url": "https://bidplus.gem.gov.in/showbidDocument/12345",
            "items": "Electric Cable",
            "category": "cable"
        }

        r = parser.parse_one("Raw block text")
        self.assertEqual(r["bid_no"], "GEM/2026/B/12345")
        # Ensure category got mapped to standard name ("Cable") via map_category fallback
        self.assertEqual(r["category"], "Cable")

    @patch('llm.llm_parse_tender')
    def test_parser_parse_one_llm_fallback(self, mock_llm_parse):
        # Enable LLM parsing in settings
        db.save_setting("llm_provider", "Google AI Studio (Gemini)")
        db.save_setting("llm_api_key", "test_key")
        db.save_setting("llm_use_parsing", True)

        # Force LLM parser to fail
        mock_llm_parse.side_effect = Exception("API rate limit exceeded")

        # Paste block that regex parser CAN handle
        text = """
        BID NO: GEM/2026/B/7526729
        Items: Computer System
        Quantity: 58
        """
        r = parser.parse_one(text)
        # Verify it falls back successfully to regex parser
        self.assertEqual(r["bid_no"], "GEM/2026/B/7526729")
        self.assertEqual(r["items"], "Computer System")
        self.assertEqual(r["quantity"], "58")

    @patch('llm.llm_map_category')
    def test_parser_map_category_with_llm(self, mock_llm_map):
        # Enable LLM mapping in settings
        db.save_setting("llm_provider", "Google AI Studio (Gemini)")
        db.save_setting("llm_api_key", "test_key")
        db.save_setting("llm_use_mapping", True)

        mock_llm_map.return_value = "Welding Electrodes"

        res = parser.map_category("E6013 weld electrode rod")
        self.assertEqual(res, "Welding Electrodes")

    @patch('llm.llm_map_category')
    def test_parser_map_category_llm_fallback(self, mock_llm_map):
        # Enable LLM mapping in settings
        db.save_setting("llm_provider", "Google AI Studio (Gemini)")
        db.save_setting("llm_api_key", "test_key")
        db.save_setting("llm_use_mapping", True)

        # Force LLM category mapping to fail
        mock_llm_map.side_effect = Exception("API Key expired")

        # Verify it falls back successfully to keyword mapping (screen -> Ni Screen)
        res = parser.map_category("Stainless Steel Screen")
        self.assertEqual(res, "Ni Screen")

if __name__ == '__main__':
    unittest.main()
