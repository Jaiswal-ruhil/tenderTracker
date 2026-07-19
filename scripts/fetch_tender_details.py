"""
Fetch actual tender details from GeM portal for GEM/2026/B/7764637
"""

import sys
sys.path.insert(0, 'src')
sys.path.insert(0, 'src/core')

import scraper
import db
from datetime import datetime

BID_NO = "GEM/2026/B/7764637"
BID_URL = "https://bidplus.gem.gov.in/showbidDocument/7764637"

def fetch_tender_details():
    """Fetch tender details using scraper"""
    print(f"Fetching details for {BID_NO}...")
    print(f"URL: {BID_URL}")
    
    try:
        # Import logger for proper logging function
        import logger
        
        # Use scraper to fetch tender details
        print("Initializing scraper...")
        tender_data = scraper.scrape_bid_page(BID_URL, log_fn=logger.log)
        
        if tender_data:
            print("✅ Successfully fetched tender details:")
            print(f"   Category: {tender_data.get('category', 'N/A')}")
            print(f"   Items: {tender_data.get('items', 'N/A')}")
            print(f"   Est Value: {tender_data.get('est_value', 'N/A')}")
            print(f"   Department: {tender_data.get('dept', 'N/A')}")
            print(f"   Organization: {tender_data.get('org_name', 'N/A')}")
            print(f"   Location: {tender_data.get('location', 'N/A')}")
            print(f"   Quantity: {tender_data.get('quantity', 'N/A')}")
            print(f"   End Date: {tender_data.get('end_date', 'N/A')}")
            
            # Update database with fetched details
            print("\nUpdating database with fetched details...")
            tender_data['bid_no'] = BID_NO
            tender_data['bid_url'] = BID_URL
            tender_data['updated_at'] = datetime.now().isoformat()
            
            db.upsert_tender(tender_data)
            print("✅ Database updated successfully")
            
            return tender_data
        else:
            print("❌ Failed to fetch tender details")
            return None
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    tender_data = fetch_tender_details()
    if tender_data:
        print("\n🎉 Tender details fetched and updated successfully")
    else:
        print("\n❌ Failed to fetch tender details")
