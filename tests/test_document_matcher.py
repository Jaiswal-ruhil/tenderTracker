import os
import sys
import unittest
from unittest.mock import patch

# Ensure src paths are in sys.path
_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, os.path.join(_ROOT, "src", "core"))
sys.path.insert(0, os.path.join(_ROOT, "src", "gui"))
sys.path.insert(0, os.path.join(_ROOT, "src", "core", "parsers"))
sys.path.insert(0, os.path.join(_ROOT, "src", "core", "ai"))
sys.path.insert(0, os.path.join(_ROOT, "src", "core", "workflow"))

import document_matcher


class DummyMatcher(document_matcher.DocumentMatcherMixin):
    def __init__(self):
        self.filing_folder = os.path.join("dummy_base", "filing_folder")
        self.category = "general"
        self.matched_documents = {}
        self.missing_documents = []

    def _log(self, level, msg, details=None):
        pass


class TestDocumentMatcher(unittest.TestCase):
    def setUp(self):
        self.matcher = DummyMatcher()

    def test_calculate_similarity_score(self):
        # Exact match formula score
        self.assertAlmostEqual(self.matcher._calculate_similarity_score("experience", "experience"), 0.96, places=2)
        # Substring match
        score = self.matcher._calculate_similarity_score("experience criteria", "experience")
        self.assertGreater(score, 0.6)

    def test_is_category_specific_doc(self):
        self.assertFalse(self.matcher._is_category_specific_doc("GST Certificate"))
        self.assertFalse(self.matcher._is_category_specific_doc("PAN Card"))
        self.assertFalse(self.matcher._is_category_specific_doc("Turnover Certificate"))
        self.assertTrue(self.matcher._is_category_specific_doc("ISO 9001 Compliance Certificate"))
        self.assertTrue(self.matcher._is_category_specific_doc("Boiler Special Quality ATC Requirement"))

    def test_ai_enhanced_document_matching(self):
        required_docs = [
            {'name': 'Experience Criteria', 'category': 'Technical'},
            {'name': 'Past Performance', 'category': 'Technical'},
            {'name': 'Bidder Turnover', 'category': 'Financial'},
            {'name': 'Additional Doc 1 (Requested in ATC)', 'category': 'Compliance'},
        ]
        firm_docs = {
            'work_experience': 'experience_certificate.pdf',
            'ca_turnover': 'turnover_proof.pdf',
        }

        expected_common = os.path.normpath(os.path.join("dummy_base", "COMMON"))

        def mock_exists(p):
            p_norm = os.path.normpath(p)
            return p_norm in [
                os.path.normpath("dummy_base"),
                expected_common,
                os.path.normpath(os.path.join(expected_common, 'Past_Performance_Record.pdf')),
                os.path.normpath(os.path.join(expected_common, 'MII_Declaration_ATC.pdf')),
                'experience_certificate.pdf',
                'turnover_proof.pdf'
            ]

        def mock_listdir(p):
            p_norm = os.path.normpath(p)
            if p_norm == expected_common:
                return ['Past_Performance_Record.pdf', 'MII_Declaration_ATC.pdf']
            return []

        with patch('document_matcher.os.path.exists', side_effect=mock_exists), \
             patch('document_matcher.os.path.isdir', return_value=True), \
             patch('document_matcher.os.listdir', side_effect=mock_listdir), \
             patch('document_matcher.os.path.isfile', return_value=True):

            matches = self.matcher._ai_enhanced_document_matching(required_docs, firm_docs)
            self.assertIn('Experience Criteria', matches)
            self.assertIn('Past Performance', matches)
            self.assertIn('Bidder Turnover', matches)
            self.assertIn('Additional Doc 1 (Requested in ATC)', matches)


if __name__ == "__main__":
    unittest.main()
