import re
import time

# Static import hooks for PyInstaller package scanning
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    pass

_selenium_ok = False
def _try_import_selenium():
    global _selenium_ok
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from webdriver_manager.chrome import ChromeDriverManager
        _selenium_ok = True
        return webdriver, Options, Service, By, WebDriverWait, EC, ChromeDriverManager
    except ImportError:
        return None

def _txt(el):
    try: return el.text.strip()
    except: return ""

def _cell_after(rows, label):
    """Find a <td> whose text matches label and return the next sibling td text."""
    label_l = label.lower()
    for row in rows:
        cells = row.find_elements("tag name", "td")
        for i, c in enumerate(cells):
            if label_l in c.text.lower() and i+1 < len(cells):
                val = cells[i+1].text.strip()
                if val: return val
    return ""

def _find_text(driver, label):
    """Generic: find element whose text contains label, return next sibling or parent text."""
    try:
        els = driver.find_elements("xpath",
            f"//*[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'{label.lower()}')]")
        for el in els:
            try:
                sib = el.find_element("xpath", "following-sibling::*[1]")
                t = sib.text.strip()
                if t and t.lower() != label.lower(): return t
            except: pass
            try:
                parent_text = el.find_element("xpath","..").text
                cleaned = re.sub(re.escape(el.text),"",parent_text,count=1).strip()
                if cleaned and len(cleaned)<200: return cleaned
            except: pass
    except: pass
    return ""

def scrape_bid_page(url, log_fn=None):
    """
    Open the GeM bid document page with Selenium and extract all available fields.
    Returns a dict of extra fields to merge into the record.
    """
    mods = _try_import_selenium()
    if not mods:
        if log_fn: log_fn("err","Selenium not installed. Run: pip install selenium webdriver-manager")
        return {}

    webdriver, Options, Service, By, WebDriverWait, EC, ChromeDriverManager = mods

    opts = Options()
    # Run visible so GeM doesn't block headless browsers
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument("--start-maximized")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    # Comment the next line to see the browser window
    # opts.add_argument("--headless=new")

    extra = {}
    driver = None
    try:
        if log_fn: log_fn("info", f"  Opening Chrome → {url}")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=opts)
        driver.execute_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")

        driver.get(url)
        # wait for page body
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(3)   # let JS render

        page = driver.page_source

        def regex_page(pattern, flags=re.I|re.S):
            m = re.search(pattern, page, flags)
            return m.group(1).strip() if m else ""

        # ── field extractions from page HTML ──────────────────────────────────

        # Bid Opening Date
        extra["bid_opening"] = regex_page(
            r"Bid Opening Date[^<]*?</?\w*[^>]*>\s*([0-9]{2}[-/][0-9]{2}[-/][0-9]{4}[^<]{0,20})")

        # Estimated Bid Value
        extra["est_value"] = regex_page(
            r"Estimated Bid Value[^<]*?</?\w*[^>]*>\s*([0-9][0-9,\.]+)")

        # Evaluation Method
        extra["eval_method"] = regex_page(
            r"Evaluation Method[^<]*?</?\w*[^>]*>\s*([A-Za-z ]+(?:wise|based)[^<]{0,60})")

        # Ministry
        extra["ministry"] = regex_page(
            r"Ministry[/\w\s]*?Name[^<]*?</?\w*[^>]*>\s*([A-Z][^<]{3,80})")

        # Department
        dept_scraped = regex_page(
            r"Department Name[^<]*?</?\w*[^>]*>\s*([A-Z][^<]{3,80})")
        if dept_scraped: extra["dept"] = dept_scraped

        # Organisation
        extra["organisation"] = regex_page(
            r"Organisation Name[^<]*?</?\w*[^>]*>\s*([A-Z][^<]{2,60})")

        # Office
        extra["office"] = regex_page(
            r"Office Name[^<]*?</?\w*[^>]*>\s*([A-Z][^<]{2,60})")

        # Contract Duration
        extra["contract_dur"] = regex_page(
            r"Contract (?:Duration|Period)[^<]*?</?\w*[^>]*>\s*([0-9][^<]{1,30})")

        # Bid Type
        extra["bid_type"] = regex_page(
            r"Type of Bid[^<]*?</?\w*[^>]*>\s*([A-Za-z ]+Bid[^<]{0,40})")

        # Bid to RA
        ra = regex_page(r"Bid to RA enabled[^<]*?</?\w*[^>]*>\s*(Yes|No)")
        extra["bid_to_ra"] = ra if ra else regex_page(r"Bid to RA\s*</?\w*[^>]*>\s*(Yes|No)")

        # EMD
        emd = regex_page(r"EMD Detail[^<]{0,200}?Required[^<]*?</?\w*[^>]*>\s*(Yes|No)")
        extra["emd"] = emd

        # ePBG
        epbg = regex_page(r"ePBG Detail[^<]{0,200}?Required[^<]*?</?\w*[^>]*>\s*(Yes|No)")
        extra["epbg"] = epbg

        # MII Compliance
        extra["mii"] = regex_page(
            r"MII Compliance[^<]*?</?\w*[^>]*>\s*(Yes|No)")

        # MSE Purchase Preference
        extra["mse_pref"] = regex_page(
            r"MSE Purchase Preference[^<]*?</?\w*[^>]*>\s*(Yes|No)")

        # MSE Relaxation
        extra["mse_relax"] = regex_page(
            r"MSE Relaxation[^<]{0,60}?</?\w*[^>]*>\s*(Yes|No)")

        # Startup Relaxation
        extra["startup_relax"] = regex_page(
            r"Startup Relaxation[^<]{0,60}?</?\w*[^>]*>\s*(Yes|No)")

        # Min Turnover
        extra["min_turnover"] = regex_page(
            r"(?:Minimum Average Annual Turnover|Average Turn Over)[^<]{0,60}?</?\w*[^>]*>\s*([0-9][^<]{0,20})")

        # Experience years
        extra["exp_years"] = regex_page(
            r"Years of Past Experience[^<]{0,60}?</?\w*[^>]*>\s*([0-9][^<]{0,20})")

        # Consignee / delivery location
        loc = regex_page(
            r"Consignee[^<]{0,100}?Address[^<]*?</?\w*[^>]*>\s*([A-Z][^<]{5,120})")
        if not loc:
            loc = regex_page(r"Delivery Location[^<]*?</?\w*[^>]*>\s*([A-Z][^<]{5,80})")
        extra["location"] = loc

        # Category (item category)
        cat = regex_page(r"Item Category[^<]*?</?\w*[^>]*>\s*([A-Z][^<]{3,80})")
        if not cat:
            cat = regex_page(r"Similar Category[^<]*?</?\w*[^>]*>\s*([A-Z][^<]{3,80})")
        extra["category"] = cat

        # Remove empty values
        extra = {k:v for k,v in extra.items() if v}

        if log_fn:
            log_fn("ok", f"  Scraped {len(extra)} extra fields: {', '.join(extra.keys())}")

    except Exception as e:
        if log_fn: log_fn("err", f"  Selenium error: {e}")
    finally:
        if driver:
            try: driver.quit()
            except: pass

    return extra
