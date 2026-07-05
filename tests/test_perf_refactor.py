import sys
import os
import unittest
import json
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

# Add src and core to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'core'))

import parser
import db
from llm_client import LMStudioClient, calculate_bid_hash, ClassificationResult
import mcp_server

class TestPerfRefactor(unittest.TestCase):
    def setUp(self):
        # Setup temporary test database
        self.old_db = db.DB_FILE
        self.old_settings = db.SETTINGS_FILE
        db.DB_FILE = os.path.join(os.path.dirname(__file__), "test_perf_refactor.db")
        db.SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "test_perf_refactor_settings.json")
        
        if os.path.exists(db.DB_FILE):
            try: os.remove(db.DB_FILE)
            except: pass
        if os.path.exists(db.SETTINGS_FILE):
            try: os.remove(db.SETTINGS_FILE)
            except: pass
            
        # Initialize test tables
        db.init_db_connection()

    def tearDown(self):
        if os.path.exists(db.DB_FILE):
            try: os.remove(db.DB_FILE)
            except: pass
        if os.path.exists(db.SETTINGS_FILE):
            try: os.remove(db.SETTINGS_FILE)
            except: pass
        db.DB_FILE = self.old_db
        db.SETTINGS_FILE = self.old_settings

    def test_clean_raw_text(self):
        raw_text = (
            "GEM | Government Marketplace\n"
            "BID NO: GEM/2026/B/1234567\n"
            "page 1 of 5\n"
            "Items: Safety Helmet\n"
            "1 / 4\n"
            "Department: SafeCorp\n"
        )
        cleaned = parser.clean_raw_text(raw_text)
        self.assertNotIn("GEM | Government Marketplace", cleaned)
        self.assertNotIn("page 1 of 5", cleaned)
        self.assertIn("BID NO: GEM/2026/B/1234567", cleaned)
        self.assertIn("Items: Safety Helmet", cleaned)

    def test_deterministic_parsing_no_llm(self):
        # Verify that parsing a block with invalid bid number doesn't attempt any LLM call
        raw_block = "Invalid text block with no bid number"
        res = parser.parse_one(raw_block)
        # Should return a dictionary but no bid_no
        self.assertNotIn("bid_no", res)

    def test_caching_and_hashing(self):
        bid = {
            "bid_no": "GEM/2026/B/777777",
            "items": "Oxygen Cylinder",
            "dept": "Health Dept",
            "category": "Medical Equipment"
        }
        h1 = calculate_bid_hash(bid)
        h2 = calculate_bid_hash(bid.copy())
        self.assertEqual(h1, h2)
        
        # Test Cache Set and Get
        dummy_cls = {
            "bid_no": "GEM/2026/B/777777",
            "category": "Medical Equipment",
            "subcategory": "Gas Cylinder",
            "keywords": ["oxygen", "gas"],
            "products": ["Cylinder"],
            "confidence": 0.95,
            "summary": "Oxygen Cylinder tender",
            "recommended": True
        }
        db.set_cached_classification(h1, dummy_cls)
        cached = db.get_cached_classification(h1)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["subcategory"], "Gas Cylinder")
        self.assertEqual(cached["keywords"], ["oxygen", "gas"])

    @patch('httpx.AsyncClient.post')
    def test_llm_client_classification(self, mock_post):
        # Setup mock HTTP response with think block and JSON output
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        mock_json_content = (
            "<think>\nWe are matching Oxygen Cylinders.\n</think>\n"
            "{\n"
            "  \"bid_no\": \"GEM/2026/B/888888\",\n"
            "  \"category\": \"Medical\",\n"
            "  \"subcategory\": \"Oxygen\",\n"
            "  \"keywords\": [\"oxygen\"],\n"
            "  \"products\": [\"Oxygen Tank\"],\n"
            "  \"confidence\": 0.9,\n"
            "  \"summary\": \"Tender for oxygen supply\",\n"
            "  \"recommended\": true\n"
            "}"
        )
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": mock_json_content
                }
            }]
        }
        mock_post.return_value = mock_response

        # Call classify async
        client = LMStudioClient()
        bid = {
            "bid_no": "GEM/2026/B/888888",
            "items": "Oxygen Supply",
            "category": "Medical"
        }
        
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(client.classify_bid_async(bid, force=True))
        loop.run_until_complete(client.close())
        
        self.assertEqual(result.bid_no, "GEM/2026/B/888888")
        self.assertEqual(result.subcategory, "Oxygen")
        self.assertTrue(result.recommended)
        
        # Verify classification was stored in DB classifications table
        stored = db.get_classification("GEM/2026/B/888888")
        self.assertIsNotNone(stored)
        self.assertEqual(stored["subcategory"], "Oxygen")
        self.assertEqual(stored["products"], ["Oxygen Tank"])

    @patch('httpx.AsyncClient.post')
    def test_batch_processing(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_json_content = (
            "{\n"
            "  \"bid_no\": \"GEM/2026/B/999999\",\n"
            "  \"category\": \"Cables\",\n"
            "  \"subcategory\": \"Copper\",\n"
            "  \"keywords\": [],\n"
            "  \"products\": [],\n"
            "  \"confidence\": 0.8,\n"
            "  \"summary\": \"Copper cables\",\n"
            "  \"recommended\": false\n"
            "}"
        )
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": mock_json_content
                }
            }]
        }
        mock_post.return_value = mock_response

        client = LMStudioClient()
        bids = [
            {"bid_no": f"GEM/2026/B/999999_{i}", "items": f"Cable {i}"} for i in range(15)
        ]
        
        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(client.classify_bids_batch(bids, force=True))
        loop.run_until_complete(client.close())
        
        # We expect 15 successful classifications (split into 2 batches)
        self.assertEqual(len(results), 15)

    def test_mcp_tools(self):
        # 1. extract_bid_blocks
        raw_text = "BID NO: GEM/2026/B/111111\nItems: Cable\nQuantity: 50"
        blocks = mcp_server.extract_bid_blocks(raw_text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["bid_no"], "GEM/2026/B/111111")
        
        # 2. get_bid and database operations
        db.upsert_tender(blocks[0])
        fetched = mcp_server.get_bid("GEM/2026/B/111111")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["items"], "Cable")
        
        # 3. generate_quote_requirements
        reqs = mcp_server.generate_quote_requirements(fetched)
        self.assertEqual(reqs["bid_no"], "GEM/2026/B/111111")
        self.assertTrue(any("EMD" in line for line in reqs["checklist"]))
        
        # 4. match_company_products
        prod = {
            "product_id": "P001",
            "name": "Cable",
            "description": "High voltage copper cables",
            "category": "Electrical"
        }
        db.save_product(prod)
        matches = mcp_server.match_company_products(fetched)
        self.assertEqual(matches["bid_no"], "GEM/2026/B/111111")
        self.assertGreater(matches["match_score"], 0.0)
        self.assertEqual(matches["matching_products"][0]["name"], "Cable")

if __name__ == '__main__':
    unittest.main()
