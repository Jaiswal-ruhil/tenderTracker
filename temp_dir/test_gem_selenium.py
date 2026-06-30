import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def test_pagination():
    opts = Options()
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument("--start-maximized")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.execute_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    
    try:
        driver.get("https://bidplus.gem.gov.in/all-bids")
        
        # Search
        search_input = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "searchBid"))
        )
        search_input.clear()
        search_input.send_keys("Uttar Pradesh Cooperative Sugar Factories Federation Limited")
        
        search_btn = driver.find_element(By.ID, "searchBidRA")
        search_btn.click()
        
        time.sleep(5)
        
        # Scrape page 1 summary
        body_text = driver.find_element(By.TAG_NAME, "body").text
        for line in body_text.splitlines():
            if "Showing" in line and "records" in line:
                print("PAGE 1 SUMMARY:", line)
                
        # Find first bid number on Page 1
        bid_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'BID NO:')]")
        if bid_elements:
            print("PAGE 1 FIRST BID:", bid_elements[0].text)
            
        # Click "Next"
        # We find the links with text "Next". Since there might be two, let's click the first one that is displayed.
        next_links = driver.find_elements(By.XPATH, "//a[text()='Next']")
        print(f"Found {len(next_links)} 'Next' links")
        
        if next_links:
            # Let's scroll to it and click
            driver.execute_script("arguments[0].scrollIntoView(true);", next_links[0])
            time.sleep(1)
            next_links[0].click()
            print("Clicked Next")
            
            # Wait for content to change.
            # We can wait for the showing summary to contain "Showing 11 - 20"
            time.sleep(5)
            
            body_text = driver.find_element(By.TAG_NAME, "body").text
            for line in body_text.splitlines():
                if "Showing" in line and "records" in line:
                    print("PAGE 2 SUMMARY:", line)
                    
            bid_elements_p2 = driver.find_elements(By.XPATH, "//*[contains(text(), 'BID NO:')]")
            if bid_elements_p2:
                print("PAGE 2 FIRST BID:", bid_elements_p2[0].text)
        else:
            print("No 'Next' link found!")
            
    except Exception as e:
        print("Error during test:", e)
    finally:
        driver.quit()

if __name__ == "__main__":
    test_pagination()
