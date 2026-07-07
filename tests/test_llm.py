import sys
import os
import unittest
import urllib.error
import json
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

        # Reset LLM module cache state for isolated tests
        llm._loaded_local_models.clear()
        llm._failed_local_models.clear()
        llm._failed_local_service_urls.clear()
        if hasattr(llm, "_failed_local_embedding_services"):
            llm._failed_local_embedding_services.clear()

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

        # Test cleaning JSON with <think>...</think> reasoning block
        self.assertEqual(llm.clean_json_response('<think>\nI should extract field x.\n{\n "nested": true\n}\n</think>\n{"test": 5}'), '{"test": 5}')
        self.assertEqual(llm.extract_thinking_block('<think>\nI should extract field x.\n</think>\n{"test": 5}'), "I should extract field x.")

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
        <think>
        Extract bid number, dates, and category from the tender body.
        </think>
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
        self.assertIn("Extract bid number", res["_llm_thinking"])

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

        r = parser.parse_one("Raw block text")
        # Under 100% deterministic parsing, LLM is never called for extraction
        self.assertNotIn("bid_no", r)
        self.assertFalse(mock_llm_parse.called)

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

        res = parser.map_category("E6013 weld rod")
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

    @patch('urllib.request.urlopen')
    def test_auto_load_local_model_ignores_error_json(self, mock_urlopen):
        # Mock /v1/models returning empty, then /models/load returning JSON error,
        # then /api/v1/models/load returning success.
        mock_response_list = MagicMock()
        mock_response_list.read.return_value = b'{"data": []}'
        mock_response_list.__enter__.return_value = mock_response_list

        mock_response_error = MagicMock()
        mock_response_error.read.return_value = b'{"error":"Unexpected endpoint or method. (POST /models/load)"}'
        mock_response_error.__enter__.return_value = mock_response_error

        mock_response_success = MagicMock()
        mock_response_success.read.return_value = b'{"status":"success"}'
        mock_response_success.__enter__.return_value = mock_response_success

        mock_urlopen.side_effect = [mock_response_list, mock_response_error, mock_response_success]

        llm.auto_load_local_model("http://localhost:1234", "my-local-model")
        self.assertEqual(mock_urlopen.call_count, 3)

    @patch('urllib.request.urlopen')
    def test_local_service_failure_caches_base_url(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"error":"Unexpected endpoint or method."}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        with self.assertRaises(ValueError):
            llm.auto_load_local_model("http://localhost:1234", "my-local-model")

        # Subsequent calls should raise from cached base URL failure without extra requests
        mock_urlopen.reset_mock()
        with self.assertRaises(ValueError):
            llm.auto_load_local_model("http://localhost:1234", "my-local-model")
        self.assertEqual(mock_urlopen.call_count, 0)

    @patch('urllib.request.urlopen')
    def test_try_local_endpoint_skips_http200_error_body(self, mock_urlopen):
        def side_effect(req, timeout=10):
            url = req.full_url
            mock_resp = MagicMock()
            mock_resp.__enter__.return_value = mock_resp
            if url.endswith("/chat/completions"):
                mock_resp.read.return_value = b'Unexpected endpoint or method. (POST /chat/completions)'
                return mock_resp
            if url.endswith("/api/v1/chat"):
                mock_resp.read.return_value = b'{"output":[{"type":"message","content":"OK"}]}'
                return mock_resp
            raise urllib.error.HTTPError(url, 404, "Not Found", hdrs=None, fp=None)

        mock_urlopen.side_effect = side_effect
        text, used = llm.try_local_endpoint(
            "http://localhost:1234",
            ["chat/completions", "api/v1/chat"],
            method="POST",
            body={"model": "local-model", "input": "test"},
            timeout=1,
        )
        self.assertTrue(used.endswith("/api/v1/chat"))
        self.assertIn("OK", text)

    @patch('urllib.request.urlopen')
    def test_call_llm_native_lm_studio_chat(self, mock_urlopen):
        def side_effect(req, timeout=15):
            url = req.full_url
            mock_resp = MagicMock()
            mock_resp.__enter__.return_value = mock_resp
            if url.endswith("/models"):
                mock_resp.read.return_value = b'{"data": [{"id": "google/gemma-4-12b-qat"}]}'
                return mock_resp
            if url.endswith("/api/v1/chat"):
                mock_resp.read.return_value = b'{"output":[{"type":"message","content":"OK"}]}'
                return mock_resp
            mock_resp.read.return_value = b'Unexpected endpoint or method.'
            return mock_resp

        mock_urlopen.side_effect = side_effect
        result = llm.call_llm(
            "Respond with exactly the word OK.",
            "Local LLM (LM Studio / Ollama)",
            "",
            "http://localhost:1234",
            "google/gemma-4-12b-qat",
        )
        self.assertEqual(result, "OK")

    @patch('urllib.request.urlopen')
    def test_is_server_reachable_local_roots(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b'{}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        self.assertTrue(llm.is_server_reachable("http://localhost:1234"))

    @patch('urllib.request.urlopen')
    def test_get_embedding_local_fallback(self, mock_urlopen):
        # First request returns a JSON error on /v1/embeddings, second request succeeds on /api/embeddings
        def side_effect(req, timeout=10):
            url = req.full_url
            mock_resp = MagicMock()
            mock_resp.__enter__.return_value = mock_resp
            if url.endswith("/v1/embeddings"):
                mock_resp.read.return_value = b'{"error":"Unexpected endpoint or method. (POST /v1/embeddings)"}'
                return mock_resp
            if url.endswith("/api/embeddings"):
                mock_resp.read.return_value = b'{"data": [{"embedding": [0.1, 0.2, 0.3]}]}'
                return mock_resp
            raise urllib.error.HTTPError(url, 404, "Not Found", hdrs=None, fp=None)

        mock_urlopen.side_effect = side_effect
        emb = llm.get_embedding("test text", "Local LLM (LM Studio / Ollama)", "", "http://localhost:1234/v1", "my-local-model")
        self.assertEqual(emb, [0.1, 0.2, 0.3])

    @patch('urllib.request.urlopen')
    def test_try_local_endpoint_preserves_body_across_retries(self, mock_urlopen):
        # The first candidate returns an HTTPError so the helper must preserve the request body for subsequent retries.
        def side_effect(req, timeout=10):
            url = req.full_url
            if url.endswith('/v1/embeddings'):
                raise urllib.error.HTTPError(url, 404, 'Not Found', hdrs=None, fp=None)
            mock_resp = MagicMock()
            mock_resp.__enter__.return_value = mock_resp
            mock_resp.read.return_value = b'{"data": [{"embedding": [0.4, 0.5, 0.6]}]}'
            # Verify the body remains the same on retry
            self.assertEqual(req.data, json.dumps({"model": "my-local-model", "input": "test text"}).encode('utf-8'))
            return mock_resp

        mock_urlopen.side_effect = side_effect
        emb = llm.get_embedding("test text", "Local LLM (LM Studio / Ollama)", "", "http://localhost:1234/v1", "my-local-model")
        self.assertEqual(emb, [0.4, 0.5, 0.6])

    @patch('urllib.request.urlopen')
    def test_try_local_endpoint_http_error_includes_url(self, mock_urlopen):
        # Simulate an HTTPError from the first candidate and ensure the final error includes the endpoint URL.
        error = urllib.error.HTTPError(
            "http://localhost:1234/v1/embeddings", 404, "Not Found", hdrs=None, fp=None
        )
        mock_urlopen.side_effect = error

        with self.assertRaises(ValueError) as cm:
            llm.try_local_endpoint("http://localhost:1234/v1", "embeddings", timeout=1)
        self.assertIn("/embeddings", str(cm.exception))
        self.assertIn("HTTPError 404", str(cm.exception))

    @patch('llm.llm_parse_tender')
    def test_parser_level_1_regex_fail_llm_fallback(self, mock_llm_parse):
        # Enable LLM provider but keep use_parsing disabled
        db.save_setting("llm_provider", "Google AI Studio (Gemini)")
        db.save_setting("llm_api_key", "test_key")
        db.save_setting("llm_use_parsing", False)

        # Raw text without valid bid no format
        text = "This is a random text block without any bid number."
        r = parser.parse_one(text)
        self.assertNotIn("bid_no", r)
        self.assertFalse(mock_llm_parse.called)

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

    @patch('llm_client.LMStudioClient.classify_bids_batch')
    @patch('gui_workers._llm_module.llm_parse_tender')
    @patch('gui_workers.parse_one')
    def test_do_parse_force_llm_true(self, mock_parse_one, mock_llm_parse, mock_classify):
        mock_classify.return_value = []
        # Setup sync thread execution for target='worker' only
        import threading
        original_thread = threading.Thread
        def mock_thread_init(*args, **kwargs):
            target = kwargs.get('target')
            if target and target.__name__ == 'worker':
                class SyncThread:
                    def start(self):
                        target()
                return SyncThread()
            return original_thread(*args, **kwargs)
        
        # Setup settings
        db.save_setting("llm_provider", "Google AI Studio (Gemini)")
        db.save_setting("llm_api_key", "test_key")
        db.save_setting("llm_use_parsing", False) # disable setting to test force override
        
        # Setup mock app
        from gui_workers import WorkersMixin
        class MockApp(WorkersMixin):
            def __init__(self):
                self.paste_txt = MagicMock()
                self.paste_txt.get.return_value = "BID NO: GEM/2026/B/12345"
                self._records = []
                self.logs = []
                
            def _log(self, level, msg):
                self.logs.append((level, msg))
            def _set_prog(self, val, msg):
                pass
            def after(self, ms, callback):
                callback()
            def _is_bid_in_dont_wants(self, bid):
                return None
            def _add_single_row_immediate(self, rec, stats):
                self._records.append(rec)
                stats["added"] += 1
            def _finalize_parse(self, recs, stats, total, start_time):
                pass
            def _set_status(self, msg, color=None):
                pass
                
        app = MockApp()
        mock_llm_parse.return_value = {"bid_no": "GEM/2026/B/12345", "items": "Test Item"}
        
        with patch('threading.Thread', side_effect=mock_thread_init):
            app._do_parse(force_llm=True)
        
        # Verify LLM parser was called because force_llm=True overrides setting
        mock_llm_parse.assert_called_once()
        self.assertEqual(len(app._records), 1)
        self.assertEqual(app._records[0]["bid_no"], "GEM/2026/B/12345")

    @patch('llm_client.LMStudioClient.classify_bids_batch')
    @patch('gui_workers._llm_module.llm_parse_tender')
    @patch('gui_workers.parse_one')
    def test_do_parse_force_llm_false(self, mock_parse_one, mock_llm_parse, mock_classify):
        mock_classify.return_value = []
        # Setup sync thread execution for target='worker' only
        import threading
        original_thread = threading.Thread
        def mock_thread_init(*args, **kwargs):
            target = kwargs.get('target')
            if target and target.__name__ == 'worker':
                class SyncThread:
                    def start(self):
                        target()
                return SyncThread()
            return original_thread(*args, **kwargs)
        
        # Setup settings
        db.save_setting("llm_provider", "Google AI Studio (Gemini)")
        db.save_setting("llm_api_key", "test_key")
        db.save_setting("llm_use_parsing", True) # enable setting to test force override
        
        # Setup mock app
        from gui_workers import WorkersMixin
        class MockApp(WorkersMixin):
            def __init__(self):
                self.paste_txt = MagicMock()
                self.paste_txt.get.return_value = "BID NO: GEM/2026/B/12345"
                self._records = []
                self.logs = []
                
            def _log(self, level, msg):
                self.logs.append((level, msg))
            def _set_prog(self, val, msg):
                pass
            def after(self, ms, callback):
                callback()
            def _is_bid_in_dont_wants(self, bid):
                return None
            def _add_single_row_immediate(self, rec, stats):
                self._records.append(rec)
                stats["added"] += 1
            def _finalize_parse(self, recs, stats, total, start_time):
                pass
            def _set_status(self, msg, color=None):
                pass
                
        app = MockApp()
        mock_parse_one.return_value = {"bid_no": "GEM/2026/B/12345", "items": "Test Item"}
        
        with patch('threading.Thread', side_effect=mock_thread_init):
            app._do_parse(force_llm=False)
        
        # Verify regex parser was called and LLM was NOT called because force_llm=False overrides setting
        mock_parse_one.assert_called()
        self.assertFalse(mock_llm_parse.called)

if __name__ == '__main__':
    unittest.main()
