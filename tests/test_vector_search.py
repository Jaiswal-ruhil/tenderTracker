import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'core'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'gui'))

import unittest
from unittest.mock import patch, MagicMock
import json

import db
import vector_search

class TestVectorSearch(unittest.TestCase):
    def setUp(self):
        # Isolation is handled by conftest.py (mongomock fresh instance per test)
        pass

    def tearDown(self):
        pass

    def test_get_tender_embedding_text(self):
        rec = {
            "items": "Armoured Cable",
            "category": "Cable",
            "organisation": "BEL",
            "dept": "Ministry of Defence",
            "location": "Ghaziabad"
        }
        text = vector_search.get_tender_embedding_text(rec)
        self.assertEqual(text, "Armoured Cable Cable BEL Ministry of Defence Ghaziabad")

    @patch('db.load_all_tenders')
    def test_rebuild_vector_index(self, mock_load):
        # Setup mock tenders with cached embeddings
        mock_load.return_value = [
            {"bid_no": "GEM/2026/B/1", "items": "Laptops", "embedding": [0.1, 0.2, 0.3]},
            {"bid_no": "GEM/2026/B/2", "items": "Desktops", "embedding": [0.4, 0.5, 0.6]}
        ]
        
        success = vector_search.rebuild_vector_index()
        self.assertTrue(success)
        self.assertEqual(len(vector_search._bid_nos), 2)
        self.assertEqual(vector_search._dimension, 3)
        self.assertIsNotNone(vector_search._faiss_index)

    @patch('llm.get_embedding')
    @patch('db.load_all_tenders')
    def test_semantic_search(self, mock_load, mock_get_emb):
        # Setup mock tenders
        mock_load.return_value = [
            {"bid_no": "GEM/2026/B/1", "items": "Laptops", "embedding": [1.0, 0.0, 0.0]},
            {"bid_no": "GEM/2026/B/2", "items": "Desktops", "embedding": [0.0, 1.0, 0.0]}
        ]
        
        # Save settings for LLM configuration
        db.save_setting("llm_provider", "Google AI Studio (Gemini)")
        db.save_setting("llm_api_key", "mock_key")
        
        # Rebuild index first
        vector_search.rebuild_vector_index()
        
        # Mock query embedding: query is close to Laptops (first item)
        mock_get_emb.return_value = [0.9, 0.1, 0.0]
        
        results = vector_search.semantic_search("Laptops query")
        self.assertEqual(len(results), 2)
        
        # The first match should be GEM/2026/B/1 because it has higher cosine/lower L2 distance to [1,0,0]
        self.assertEqual(results[0][0], "GEM/2026/B/1")

if __name__ == '__main__':
    unittest.main()
