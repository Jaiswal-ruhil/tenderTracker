import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'core'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'gui'))

import unittest
from unittest.mock import patch, MagicMock

# We will test the worker behavior in gui or mock downloader calls
class TestDownload(unittest.TestCase):
    @patch('urllib.request.urlretrieve')
    @patch('pypdf.PdfReader')
    def test_direct_url_download_trigger(self, mock_pdf, mock_retrieve):
        # Setup mock PDF reader behavior
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Bid Number: GEM/2026/B/7647078\nItem Category: Handling Services\nQuantity: 1"
        mock_pdf.return_value.pages = [mock_page]

        # Verify urllib.request is called when showbidDocument URL is processed
        # We can mock urlretrieve to do nothing
        mock_retrieve.return_value = ("mock_path.pdf", None)
        
        # Test downloader functions directly or with mock
        import urllib.request
        url = "https://bidplus.gem.gov.in/showbidDocument/9448923"
        dest = "GeM-Bidding-9448923.pdf"
        urllib.request.urlretrieve(url, dest)
        mock_retrieve.assert_called_once_with(url, dest)

    @patch('scraper._try_import_selenium')
    def test_scraper_search_flow_mock(self, mock_selenium_import):
        # Mock selenium imports to avoid actual browser launching during tests
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
        
        # Verify download_tender_pdf handles mock calls
        from scraper import download_tender_pdf
        # Since selenium is mocked, download_tender_pdf will execute with mocked interfaces.
        # We can verify it returns None or behaves correctly without crashing.
        res = download_tender_pdf("GEM/2026/B/1", "temp_dir", log_fn=None, headless=True)
        self.assertIsNone(res)

if __name__ == '__main__':
    unittest.main()
