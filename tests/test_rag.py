import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'core'))

import db
import llm
import vector_search

class TestRAG(unittest.TestCase):
    def setUp(self):
        # Isolation is handled by conftest.py (mongomock fresh instance per test)
        db.init_db_connection()

    def tearDown(self):
        pass

    def test_get_tender(self):
        tender = {
            "bid_no": "GEM/2026/B/12345",
            "items": "High speed motor",
            "category": "Motor",
            "organisation": "BEL",
            "dept": "Ministry of Defence",
            "location": "Ghaziabad",
            "quantity": "5"
        }
        db.upsert_tender(tender)
        
        # Test finding existing tender
        retrieved = db.get_tender("GEM/2026/B/12345")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["bid_no"], "GEM/2026/B/12345")
        self.assertEqual(retrieved["items"], "High speed motor")
        self.assertEqual(retrieved["category"], "Motor")
        
        # Test finding non-existing tender
        self.assertNil = db.get_tender("GEM/2026/B/99999")
        self.assertIsNone(self.assertNil)

    @patch('vector_search.semantic_search')
    def test_get_similar_past_examples_fallback(self, mock_semantic_search):
        # Semantic search returns empty list (no embeddings cached)
        mock_semantic_search.return_value = []
        
        # Store a past tender to match keyword overlap
        tender = {
            "bid_no": "GEM/2026/B/99991",
            "items": "Welding Electrode 3.15mm",
            "category": "Electrodes",
            "organisation": "NTPC",
            "dept": "Power"
        }
        db.upsert_tender(tender)
        
        # Call with keyword matching "Welding Electrode"
        examples = llm.get_similar_past_examples("Need welding electrode rod")
        self.assertIn("GEM/2026/B/99991", examples)
        self.assertIn("Electrodes", examples)
        self.assertTrue(mock_semantic_search.called)

    @patch('vector_search.semantic_search')
    def test_get_similar_past_examples_semantic(self, mock_semantic_search):
        # Store a tender
        tender = {
            "bid_no": "GEM/2026/B/99992",
            "items": "Industrial Oxygen Refilling",
            "category": "Oxygen",
            "organisation": "IOCL",
            "dept": "Oil"
        }
        db.upsert_tender(tender)
        
        # Mock semantic search to return this bid
        mock_semantic_search.return_value = [("GEM/2026/B/99992", 0.05)]
        
        examples = llm.get_similar_past_examples("oxygen refill")
        self.assertIn("GEM/2026/B/99992", examples)
        self.assertIn("Oxygen", examples)
        self.assertTrue(mock_semantic_search.called)

    @patch('vector_search.semantic_search')
    def test_get_similar_category_examples_fallback(self, mock_semantic_search):
        # Semantic search returns empty list
        mock_semantic_search.return_value = []
        
        # Store category associations
        tender = {
            "bid_no": "GEM/2026/B/99993",
            "items": "Submersible Water Pump",
            "category": "Motor",
            "organisation": "BSNL",
            "dept": "Telecom"
        }
        db.upsert_tender(tender)
        
        examples = llm.get_similar_category_examples("Water Pump")
        self.assertIn("Submersible Water Pump", examples)
        self.assertIn("Motor", examples)
        self.assertTrue(mock_semantic_search.called)

    @patch('vector_search.semantic_search')
    def test_get_similar_category_examples_semantic(self, mock_semantic_search):
        # Store category associations
        tender = {
            "bid_no": "GEM/2026/B/99994",
            "items": "Armoured Power Cable",
            "category": "Cable",
            "organisation": "HAL",
            "dept": "Aviation"
        }
        db.upsert_tender(tender)
        
        # Mock semantic search to return this bid
        mock_semantic_search.return_value = [("GEM/2026/B/99994", 0.1)]
        
        examples = llm.get_similar_category_examples("Power Cable")
        self.assertIn("Armoured Power Cable", examples)
        self.assertIn("Cable", examples)
        self.assertTrue(mock_semantic_search.called)

    def test_comments_in_rag_and_embedding(self):
        # 1. Test database comments field upsert and retrieve
        tender = {
            "bid_no": "GEM/2026/B/99995",
            "items": "Laptop computer",
            "category": "Computer",
            "organisation": "DRDO",
            "dept": "Ministry of Defence",
            "comments": "This is a very high priority requirement for the lab."
        }
        db.upsert_tender(tender)
        
        retrieved = db.get_tender("GEM/2026/B/99995")
        self.assertEqual(retrieved.get("comments"), "This is a very high priority requirement for the lab.")
        
        # 2. Test get_tender_embedding_text includes comments
        embedding_text = vector_search.get_tender_embedding_text(retrieved)
        self.assertIn("This is a very high priority requirement for the lab.", embedding_text)
        
        # 3. Test get_similar_past_examples includes comments in few-shot example JSON
        examples = llm.get_similar_past_examples("Laptop computer for lab")
        self.assertIn('"comments": "This is a very high priority requirement for the lab."', examples)

    def test_comments_active_learning(self):
        # Setup initial record
        tender = {
            "bid_no": "GEM/2026/B/7721923_test",
            "items": "Refilling of Industrial Gases ...",
            "category": "Refilling Of Industrial Gases ...",
            "dept": "Uttar Pradesh Cooperative Sugar Factories Federation Limited",
            "organisation": "",
            "comments": "you missed this... Sahkari Chini Mills Ltd. Sultanpur ... thi shoud map organization KSCM Sultanpur"
        }
        db.upsert_tender(tender)
        
        # Verify settings does not have this mapping yet
        settings = db.load_settings()
        mappings = settings.get("value_mappings", [])
        original_mapping_count = len(mappings)
        
        # Run active learning
        db.apply_active_learning_from_comments()
        
        # Verify the record organisation is updated
        updated = db.get_tender("GEM/2026/B/7721923_test")
        self.assertEqual(updated.get("organisation"), "KSCM Sultanpur")
        
        # Verify settings has been updated with value mapping
        new_settings = db.load_settings()
        new_mappings = new_settings.get("value_mappings", [])
        self.assertEqual(len(new_mappings), original_mapping_count + 1)
        self.assertEqual(new_mappings[-1]["field"], "organisation")
        self.assertEqual(new_mappings[-1]["phrase"], "Sahkari Chini Mills Ltd.")
        self.assertEqual(new_mappings[-1]["key"], "KSCM Sultanpur")

if __name__ == '__main__':
    unittest.main()
