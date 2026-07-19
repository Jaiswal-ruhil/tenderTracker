"""
Test script for MCP workflow testing
Tests the full workflow from tender retrieval through filing preparation
"""

import sys
sys.path.insert(0, 'src')
sys.path.insert(0, 'src/core')

import db
import asyncio
from datetime import datetime

# Test tender ID
TEST_BID_NO = "GEM/2026/B/7764637"

def print_section(title: str):
    """Print a section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def test_catalog_get_bid():
    """Test Catalog MCP - Get tender details"""
    print_section("TEST 1: Catalog MCP - Get Tender Details")
    
    try:
        tender = None
        all_tenders = db.load_all_tenders()
        for t in all_tenders:
            if t.get("bid_no") == TEST_BID_NO:
                tender = t
                break
        
        if tender:
            print(f"✅ SUCCESS: Found tender {TEST_BID_NO}")
            print(f"   Category: {tender.get('category', 'N/A')}")
            print(f"   Items: {tender.get('items', 'N/A')}")
            print(f"   Est Value: {tender.get('est_value', 'N/A')}")
            print(f"   End Date: {tender.get('end_date', 'N/A')}")
            print(f"   Department: {tender.get('dept', 'N/A')}")
            print(f"   Location: {tender.get('location', 'N/A')}")
            print(f"   Filing Status: {tender.get('filing_status', 'N/A')}")
            return tender
        else:
            print(f"❌ FAILED: Tender {TEST_BID_NO} not found in database")
            print(f"   Total tenders in database: {len(all_tenders)}")
            return None
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def test_analysis_classify(tender: dict):
    """Test Analysis MCP - Classify tender"""
    print_section("TEST 2: Analysis MCP - Classify Tender")
    
    try:
        from llm_client import LMStudioClient
        
        async def classify():
            client = LMStudioClient()
            try:
                result = await client.classify_bid_async(tender)
                return result
            finally:
                await client.close()
        
        result = asyncio.run(classify())
        
        if result:
            print(f"✅ SUCCESS: Tender classified")
            print(f"   Category: {result.category}")
            print(f"   Confidence: {result.confidence}")
            print(f"   Reasoning: {result.reasoning[:200] if result.reasoning else 'N/A'}...")
            return result
        else:
            print(f"❌ FAILED: Classification returned None")
            return None
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def test_analysis_requirements(tender: dict):
    """Test Analysis MCP - Generate quote requirements"""
    print_section("TEST 3: Analysis MCP - Generate Quote Requirements")
    
    try:
        import llm
        
        async def generate_requirements():
            result = await llm.generate_quote_requirements_async(tender)
            return result
        
        result = asyncio.run(generate_requirements())
        
        if result:
            print(f"✅ SUCCESS: Quote requirements generated")
            print(f"   EMD Required: {result.get('emd_required', 'N/A')}")
            print(f"   ePBG Required: {result.get('epbg_required', 'N/A')}")
            print(f"   Turnover Required: {result.get('turnover_required', 'N/A')}")
            print(f"   Experience Required: {result.get('experience_required', 'N/A')}")
            return result
        else:
            print(f"❌ FAILED: Requirements generation returned None")
            return None
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def test_analysis_match_products(tender: dict):
    """Test Analysis MCP - Match company products"""
    print_section("TEST 4: Analysis MCP - Match Company Products")
    
    try:
        import llm
        
        async def match_products():
            result = await llm.match_company_products_async(tender)
            return result
        
        result = asyncio.run(match_products())
        
        if result:
            print(f"✅ SUCCESS: Product matching completed")
            print(f"   Matched Products: {len(result.get('matched_products', []))}")
            for product in result.get('matched_products', [])[:3]:
                print(f"   - {product.get('name', 'N/A')} (confidence: {product.get('confidence', 'N/A')})")
            print(f"   Overall Match Score: {result.get('overall_match_score', 'N/A')}")
            return result
        else:
            print(f"❌ FAILED: Product matching returned None")
            return None
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def test_filing_prepare(tender: dict):
    """Test Filing MCP - Prepare filing pack"""
    print_section("TEST 5: Filing MCP - Prepare Filing Pack")
    
    try:
        from filing_workflow import FilingWorkflow
        
        # First check what PDF would be downloaded
        print(f"Checking tender PDF download for {tender.get('bid_no')}...")
        print(f"Bid URL: {tender.get('bid_url')}")
        print(f"Existing PDF path: {tender.get('pdf_path', 'None')}")
        
        workflow = FilingWorkflow()
        # Skip actual filing process to avoid wrong downloads
        print("⚠️  SKIPPING actual filing preparation due to incorrect file downloads")
        print("   Issue: Filing workflow downloads wrong tender documents")
        print("   Need to fix PDF download logic to use correct tender ID")
        
        return None
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def test_filing_validate(tender: dict):
    """Test Filing MCP - Validate documents"""
    print_section("TEST 6: Filing MCP - Validate Document Integrity")
    
    try:
        from filing_workflow import FilingWorkflow
        
        workflow = FilingWorkflow()
        
        # First prepare filing to have documents to validate
        result = workflow.start_filing_process(tender, firm_name=None)
        
        if result and hasattr(workflow, 'validation_results'):
            print(f"✅ SUCCESS: Document validation completed")
            print(f"   Total Documents Validated: {len(workflow.validation_results)}")
            
            # Show validation details
            for doc_name, validation in list(workflow.validation_results.items())[:3]:
                print(f"   - {doc_name}:")
                print(f"     Valid: {validation.get('valid', False)}")
                print(f"     File Size: {validation.get('file_size', 'N/A')}")
                print(f"     Page Count: {validation.get('page_count', 'N/A')}")
                if not validation.get('valid', True):
                    print(f"     Errors: {validation.get('errors', [])}")
            
            return workflow.validation_results
        else:
            print(f"❌ FAILED: Document validation returned no results")
            return None
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def test_filing_gem_mapping(tender: dict):
    """Test Filing MCP - Get GEM requirements mapping"""
    print_section("TEST 7: Filing MCP - Get GEM Requirements Mapping")
    
    try:
        from filing_workflow import FilingWorkflow
        
        workflow = FilingWorkflow()
        
        # Get GEM requirements mapping
        mapping = workflow.get_gem_requirements_mapping(tender)
        
        if mapping:
            print(f"✅ SUCCESS: GEM requirements mapping retrieved")
            print(f"   Total Mapped Fields: {len(mapping)}")
            
            # Show some mappings
            for field, info in list(mapping.items())[:5]:
                print(f"   - {field}: {info.get('description', 'N/A')}")
                print(f"     Required: {info.get('required', False)}")
                print(f"     Document Type: {info.get('document_type', 'N/A')}")
            
            return mapping
        else:
            print(f"❌ FAILED: GEM mapping returned None")
            return None
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main test execution"""
    print_section("MCP WORKFLOW TEST SUITE")
    print(f"Testing Tender ID: {TEST_BID_NO}")
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test 1: Get tender details
    tender = test_catalog_get_bid()
    
    if not tender:
        print("\n❌ CANNOT CONTINUE: Tender not found in database")
        print("Please ensure the tender exists in the database before running tests.")
        return
    
    # Test 2: Classify tender
    classification = test_analysis_classify(tender)
    
    # Test 3: Generate quote requirements
    requirements = test_analysis_requirements(tender)
    
    # Test 4: Match company products
    product_match = test_analysis_match_products(tender)
    
    # Test 5: Prepare filing pack
    filing_result = test_filing_prepare(tender)
    
    # Test 6: Validate documents
    validation = test_filing_validate(tender)
    
    # Test 7: Get GEM requirements mapping
    gem_mapping = test_filing_gem_mapping(tender)
    
    # Final summary
    print_section("TEST SUMMARY")
    print(f"Tender ID: {TEST_BID_NO}")
    print(f"Catalog MCP (Get Tender): {'✅ PASS' if tender else '❌ FAIL'}")
    print(f"Analysis MCP (Classify): {'✅ PASS' if classification else '❌ FAIL'}")
    print(f"Analysis MCP (Requirements): {'✅ PASS' if requirements else '❌ FAIL'}")
    print(f"Analysis MCP (Product Match): {'✅ PASS' if product_match else '❌ FAIL'}")
    print(f"Filing MCP (Prepare): {'✅ PASS' if filing_result else '❌ FAIL'}")
    print(f"Filing MCP (Validate): {'✅ PASS' if validation else '❌ FAIL'}")
    print(f"Filing MCP (GEM Mapping): {'✅ PASS' if gem_mapping else '❌ FAIL'}")
    
    total_tests = 7
    passed_tests = sum([bool(tender), bool(classification), bool(requirements), 
                       bool(product_match), bool(filing_result), bool(validation), bool(gem_mapping)])
    
    print(f"\nOverall: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 ALL TESTS PASSED!")
    else:
        print(f"⚠️  {total_tests - passed_tests} test(s) failed")

if __name__ == "__main__":
    main()
