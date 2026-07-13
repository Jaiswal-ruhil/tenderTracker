import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'core')))

import form_filling_agent
import mcp_filing_server


class TestFormFillingAgent(unittest.TestCase):
    
    def setUp(self):
        self.agent = form_filling_agent.FormFillingAgent(log_fn=lambda *_: None)

    @patch('scraper._try_import_selenium')
    def test_initialize_browser(self, mock_import):
        # Setup mocks
        mock_webdriver = MagicMock()
        mock_options = MagicMock()
        mock_service = MagicMock()
        mock_wait = MagicMock()
        mock_ec = MagicMock()
        mock_manager = MagicMock()
        
        mock_import.return_value = (
            mock_webdriver, mock_options, mock_service, MagicMock(), mock_wait, mock_ec, mock_manager
        )
        
        # Test initialization
        self.agent.initialize_browser()
        
        self.assertIsNotNone(self.agent.driver)
        mock_webdriver.Chrome.assert_called()

    def test_map_to_portal_label(self):
        self.assertEqual(self.agent._map_to_portal_label("gst"), "GST Certificate")
        self.assertEqual(self.agent._map_to_portal_label("pan"), "PAN Card")
        self.assertEqual(self.agent._map_to_portal_label("custom_field"), "custom_field")

    @patch.object(form_filling_agent.FormFillingAgent, 'initialize_browser')
    def test_login_success(self, mock_init):
        # Mock WebDriver instance
        mock_driver = MagicMock()
        mock_driver.current_url = "https://sso.gem.gov.in/ARXSSO/home/dashboard"
        self.agent.driver = mock_driver
        
        success = self.agent.gem_portal_login()
        self.assertTrue(success)
        mock_driver.get.assert_called_with("https://sso.gem.gov.in/ARXSSO/oauth/login")

    @patch.object(form_filling_agent.FormFillingAgent, 'initialize_browser')
    def test_navigate_to_bid(self, mock_init):
        mock_driver = MagicMock()
        mock_search_input = MagicMock()
        mock_search_btn = MagicMock()
        mock_participate_btn = MagicMock()
        
        mock_driver.find_element.side_effect = [
            mock_search_input,
            mock_search_btn,
            mock_participate_btn
        ]
        self.agent.driver = mock_driver
        
        success = self.agent.navigate_to_bid("GEM/2026/B/9520877")
        self.assertTrue(success)
        mock_search_input.send_keys.assert_called_with("GEM/2026/B/9520877")
        mock_participate_btn.click.assert_called()

    @patch('os.path.exists', return_value=True)
    @patch.object(form_filling_agent.FormFillingAgent, 'initialize_browser')
    def test_upload_document(self, mock_init, mock_exists):
        mock_driver = MagicMock()
        mock_input = MagicMock()
        mock_driver.find_elements.return_value = [mock_input]
        self.agent.driver = mock_driver
        
        success = self.agent.upload_document("GST Certificate", "gst_path.pdf")
        self.assertTrue(success)
        mock_input.send_keys.assert_called()

    def test_mcp_tool_registration(self):
        mcp = mcp_filing_server.create_server()
        self.assertIn("execute_portal_filing", mcp._tool_manager._tools)
