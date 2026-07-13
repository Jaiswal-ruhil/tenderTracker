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
        self.old_db = db.DB_FILE
        self.old_settings = db.SETTINGS_FILE
        db.DB_FILE = os.path.join(os.path.dirname(__file__), "test_rag_tenders_db.db")
        db.SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "test_rag_settings.json")
        
        if os.path.exists(db.DB_FILE):
            try: os.remove(db.DB_FILE)
            except: pass
        if os.path.exists(db.SETTINGS_FILE):
            try: os.remove(db.SETTINGS_FILE)
            except: pass

        db.init_db_path(db.DB_FILE)
        # Create database tables
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

if __name__ == '__main__':
    unittest.main()
