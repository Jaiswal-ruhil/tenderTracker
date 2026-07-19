"""
Add test tender GEM/2026/B/7764637 to database for MCP workflow testing
"""

import sys
sys.path.insert(0, 'src')
sys.path.insert(0, 'src/core')

import db
from datetime import datetime

# Test tender data - oxygen gas refill for pipraich
TEST_TENDER = {
    "bid_no": "GEM/2026/B/7764637",
    "bid_url": "https://bidplus.gem.gov.in/showbidDocument/7764637",
    "category": "Gas",
    "items": "Oxygen Gas Refill",
    "est_value": "500000",  # Estimated value
    "start_date": "2026-07-01",
    "end_date": "2026-07-30",
    "bid_opening": "2026-07-31 10:00",
    "dept": "Department of Health",
    "org_name": "Pipraich Health Center",
    "location": "Pipraich",
    "quantity": "100",
    "unit": "Cylinders",
    "description": "Oxygen gas refill for Pipraich health center",
    "technical_criteria": "Medical grade oxygen cylinders with proper certification",
    "delivery_period": "15 days",
    "emd_required": "10000",
    "epbg_required": "25000",
    "turnover_required": "2000000",
    "experience_required": "2 years",
    "filing_status": "Evaluating",
    "tags": [],
    "comments": "",
    "created_at": datetime.now().isoformat(),
    "updated_at": datetime.now().isoformat()
}

def add_test_tender():
    """Add test tender to database"""
    print("Adding test tender to database...")
    print(f"Bid No: {TEST_TENDER['bid_no']}")
    print(f"Category: {TEST_TENDER['category']}")
    print(f"Items: {TEST_TENDER['items']}")
    print(f"Est Value: {TEST_TENDER['est_value']}")
    
    try:
        # Check if tender already exists
        existing_tenders = db.load_all_tenders()
        for tender in existing_tenders:
            if tender.get("bid_no") == TEST_TENDER["bid_no"]:
                print(f"⚠️  Tender {TEST_TENDER['bid_no']} already exists in database")
                print("Updating existing tender...")
                db.upsert_tender(TEST_TENDER)
                print("✅ Tender updated successfully")
                return True
        
        # Add new tender
        db.upsert_tender(TEST_TENDER)
        print("✅ Tender added successfully to database")
        
        # Verify
        updated_tenders = db.load_all_tenders()
        for tender in updated_tenders:
            if tender.get("bid_no") == TEST_TENDER["bid_no"]:
                print("✅ Tender verified in database")
                return True
        
        print("❌ Tender verification failed")
        return False
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = add_test_tender()
    if success:
        print("\n🎉 Test tender is now ready for MCP workflow testing")
    else:
        print("\n❌ Failed to add test tender")
