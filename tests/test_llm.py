import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'core'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'gui'))

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

    @patch('urllib.request.urlopen')
    def test_auto_load_local_model_already_loaded(self, mock_urlopen):
        # Mock /v1/models returning our model already loaded
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"data": [{"id": "my-local-model"}]}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        # Call it. It should make a GET request to /models and return immediately without POSTing to load or pull
        llm.auto_load_local_model("http://localhost:1234/v1", "my-local-model")
        
        # Verify it was called once
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch('urllib.request.urlopen')
    def test_auto_load_local_model_triggers_load(self, mock_urlopen):
        # Mock /v1/models returning empty (needs load)
        mock_response_list = MagicMock()
        mock_response_list.read.return_value = b'{"data": []}'
        mock_response_list.__enter__.return_value = mock_response_list
        
        # Mock /load endpoint returning success
        mock_response_load = MagicMock()
        mock_response_load.read.return_value = b'{"status": "success"}'
        mock_response_load.__enter__.return_value = mock_response_load
        
        mock_urlopen.side_effect = [mock_response_list, mock_response_load]
        
        llm.auto_load_local_model("http://localhost:1234/v1", "my-local-model")
        
        # Verify it did a GET to /models and then a POST to load
        self.assertEqual(mock_urlopen.call_count, 2)

    @patch('llm.llm_parse_tender')
    def test_parser_level_1_regex_fail_llm_fallback(self, mock_llm_parse):
        # Enable LLM provider but keep use_parsing disabled
        db.save_setting("llm_provider", "Google AI Studio (Gemini)")
        db.save_setting("llm_api_key", "test_key")
        db.save_setting("llm_use_parsing", False)

        mock_llm_parse.return_value = {
            "bid_no": "GEM/2026/B/99999",
            "category": "Cable",
            "items": "Armoured Cable"
        }

        # Raw text without valid bid no format
        text = "This is a random text block without any bid number."
        r = parser.parse_one(text)
        self.assertEqual(r["bid_no"], "GEM/2026/B/99999")
        self.assertTrue(mock_llm_parse.called)

    @patch('scraper._try_import_selenium')
    @patch('llm.llm_parse_tender')
    def test_scrape_bid_page_incomplete_llm_fallback(self, mock_llm_parse, mock_selenium_import):
        # Mock selenium imports
        mock_driver = MagicMock()
        mock_selenium_import.return_value = (
            MagicMock(), # webdriver
            MagicMock(), # Options
            MagicMock(), # Service
            MagicMock(), # By
            MagicMock(), # WebDriverWait
            MagicMock(), # EC
            MagicMock()  # ChromeDriverManager
        )
        
        # Mock webdriver instance
        mock_selenium_import.return_value[0].Chrome.return_value = mock_driver
        mock_driver.page_source = "<html><body>Some page text</body></html>"
        mock_driver.find_element.return_value.text = "Some body text"
        
        # Enable LLM
        db.save_setting("llm_provider", "Google AI Studio (Gemini)")
        db.save_setting("llm_api_key", "test_key")
        
        mock_llm_parse.return_value = {
            "bid_no": "GEM/2026/B/12345",
            "location": "New Delhi"
        }
        
        from scraper import scrape_bid_page
        res = scrape_bid_page("https://bidplus.gem.gov.in/showbidDocument/12345")
        self.assertEqual(res.get("location"), "New Delhi")
        self.assertTrue(mock_llm_parse.called)

if __name__ == '__main__':
    unittest.main()
