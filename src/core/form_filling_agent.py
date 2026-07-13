"""
form_filling_agent.py
~~~~~~~~~~~~~~~~~~~~~
Browser automation agent to fill bid forms and upload files on the GeM portal.
Uses Selenium to interact with the GeM portal web elements.
"""

import os
import re
import time
from typing import Dict, Any, List, Optional
import logger
import db
import scraper


class FormFillingAgent:
    """Automates form filling and document uploading on the GeM portal."""
    
    def __init__(self, log_fn=None):
        self.log_fn = log_fn or logger.log
        self.driver = None
        
    def _log(self, level: str, message: str):
        self.log_fn(level, f"[Form Filling Agent] {message}")
        
    def initialize_browser(self, headless: bool = False):
        """Initializes Chrome Selenium WebDriver."""
        self._log("info", "Initializing Chrome browser for form filling...")
        mods = scraper.import_selenium_modules()
        if not mods:
            raise ImportError("Selenium and required web drivers are not installed.")
            
        webdriver, Options, Service, By, WebDriverWait, EC, ChromeDriverManager = mods
        
        opts = Options()
        if headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1280,800")
        opts.add_argument("--start-maximized")
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=opts)
        except Exception:
            self.driver = webdriver.Chrome(options=opts)
            
        self._log("ok", "Browser initialized successfully.")
        
    def gem_portal_login(self, username: str = "") -> bool:
        """Navigates to GeM login page and guides user through authentication."""
        if not self.driver:
            self.initialize_browser()
            
        self._log("info", "Navigating to GeM login page...")
        self.driver.get("https://sso.gem.gov.in/ARXSSO/oauth/login")
        
        # In a real environment, the user must enter credentials, captcha, and potentially OTP.
        # We pause to wait for the user to authenticate successfully.
        self._log("info", "Waiting for login / MFA completion by user...")
        
        # Loop to wait until login is completed (we check for session cookies or landing page URL)
        timeout = 180  # 3 minutes maximum
        start_time = time.time()
        while time.time() - start_time < timeout:
            current_url = self.driver.current_url
            if "dashboard" in current_url.lower() or "home" in current_url.lower():
                self._log("ok", "User logged in successfully.")
                return True
            time.sleep(2)
            
        self._log("warn", "Login validation timed out.")
        return False
        
    def navigate_to_bid(self, bid_no: str) -> bool:
        """Searches and navigates to the specific bid page on the portal."""
        if not self.driver:
            self._log("error", "Browser not initialized.")
            return False
            
        self._log("info", f"Searching for Bid No: {bid_no}...")
        try:
            # Navigate to the Bids search page
            self.driver.get("https://bidplus.gem.gov.in/bid-search")
            
            # Locate search input field
            search_input = self.driver.find_element("id", "searchKey")
            search_input.clear()
            search_input.send_keys(bid_no)
            
            # Click search button
            search_btn = self.driver.find_element("id", "searchBid")
            search_btn.click()
            time.sleep(3)
            
            # Click on 'Participate' button for the matched bid
            # Element selector placeholder based on portal structure
            participate_btn = self.driver.find_element("xpath", f"//a[contains(text(), '{bid_no}')]/following::button[contains(text(), 'Participate')]")
            participate_btn.click()
            time.sleep(2)
            return True
        except Exception as e:
            self._log("error", f"Failed to navigate to bid: {e}")
            return False
            
    def fill_technical_specifications(self, specifications: Dict[str, Any]) -> bool:
        """Auto-fills technical specification forms on the portal."""
        self._log("info", "Auto-filling technical specifications...")
        # Placeholder for entering specs into the portal form
        for field, value in specifications.items():
            try:
                # Find input fields by name, ID, or label, and input values
                self._log("info", f"Filling spec field '{field}' -> '{value}'")
                # e.g., self.driver.find_element("name", field).send_keys(value)
            except Exception as e:
                self._log("warn", f"Could not fill field '{field}': {e}")
        return True
        
    def upload_document(self, label: str, file_path: str) -> bool:
        """Finds the upload element corresponding to 'label' and uploads the file."""
        if not os.path.exists(file_path):
            self._log("error", f"File to upload does not exist: {file_path}")
            return False
            
        self._log("info", f"Uploading {label} from {file_path}...")
        try:
            # Locate file input element corresponding to the label
            # Typical structure: file input element next to/nested in a container containing the label
            file_inputs = self.driver.find_elements("xpath", f"//label[contains(text(), '{label}')]/following::input[@type='file']")
            if not file_inputs:
                file_inputs = self.driver.find_elements("xpath", f"//td[contains(text(), '{label}')]/following::input[@type='file']")
                
            if file_inputs:
                file_inputs[0].send_keys(os.path.abspath(file_path))
                self._log("ok", f"Successfully uploaded {label}.")
                return True
            else:
                self._log("warn", f"Could not find file input field for: {label}")
                return False
        except Exception as e:
            self._log("error", f"Failed to upload document {label}: {e}")
            return False
            
    def upload_all_filing_pack(self, filing_folder: str, matched_docs: Dict[str, str]) -> Dict[str, bool]:
        """Uploads all matched documents from the filing folder to the GeM portal."""
        results = {}
        for doc_name, file_rel_path in matched_docs.items():
            full_path = os.path.join(filing_folder, file_rel_path)
            # Map doc name to portal field label
            portal_label = self._map_to_portal_label(doc_name)
            success = self.upload_document(portal_label, full_path)
            results[doc_name] = success
        return results
        
    def _map_to_portal_label(self, doc_name: str) -> str:
        """Maps tender Tracker document names to standard portal labels."""
        mapping = {
            "gst": "GST Certificate",
            "pan": "PAN Card",
            "experience": "Experience Criteria",
            "turnover": "Turnover Certificate",
            "bidder_undertaking": "Bidder Undertaking",
            "mii_certificate": "Local Content / MII Declaration",
            "affidavit": "Non-Blacklisting Affidavit",
        }
        return mapping.get(doc_name.lower(), doc_name)
        
    def close(self):
        """Closes browser session."""
        if self.driver:
            self.driver.quit()
            self._log("info", "Browser session closed.")
