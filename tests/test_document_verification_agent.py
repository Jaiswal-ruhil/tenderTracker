import os
import sys
import unittest
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'core')))

import document_verification_agent
import mcp_filing_server


class TestDocumentVerificationAgent(unittest.TestCase):
    
    def setUp(self):
        self.agent = document_verification_agent.DocumentVerificationAgent()

    def test_verify_gst_certificate_success(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as f:
            f.write("GSTIN: 27AAAAA1111A1Z1\nFirm Name: RK Oxygen Supplier\nAuthorized Signature and Seal")
            f_path = f.name
            
        try:
            result = self.agent.verify_compliance_document(
                file_path=f_path,
                doc_type="gst",
                expected_gstin="27AAAAA1111A1Z1",
                expected_firm_name="RK Oxygen Supplier"
            )
            self.assertTrue(result["valid"])
            self.assertTrue(result["gstin_match"])
            self.assertTrue(result["firm_name_match"])
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)

    def test_verify_gst_certificate_mismatch(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as f:
            f.write("GSTIN: 27BBBBB2222B2Z2\nFirm Name: RK Oxygen Supplier")
            f_path = f.name
            
        try:
            result = self.agent.verify_compliance_document(
                file_path=f_path,
                doc_type="gst",
                expected_gstin="27AAAAA1111A1Z1"
            )
            self.assertFalse(result["valid"])
            self.assertFalse(result["gstin_match"])
            self.assertIn("Expected GSTIN", result["errors"][0])
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)

    def test_verify_pan_card(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as f:
            f.write("Permanent Account Number: ABCDE1234F\nName: RK Oxygen Supplier")
            f_path = f.name
            
        try:
            result = self.agent.verify_compliance_document(
                file_path=f_path,
                doc_type="pan",
                expected_pan="ABCDE1234F",
                expected_firm_name="RK Oxygen Supplier"
            )
            self.assertTrue(result["valid"])
            self.assertTrue(result["pan_match"])
            self.assertTrue(result["firm_name_match"])
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)

    def test_verify_mii_certificate(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as f:
            f.write("Make in India Certificate\nTender: GEM/2026/B/9520877\nWe declare local content is 60%\nAuthorized Representative Signature")
            f_path = f.name
            
        try:
            result = self.agent.verify_compliance_document(
                file_path=f_path,
                doc_type="mii_certificate",
                expected_bid_no="GEM/2026/B/9520877",
                min_local_content=50
            )
            self.assertTrue(result["valid"])
            self.assertTrue(result["bid_no_match"])
            self.assertEqual(result["local_content_declared"], 60)
            self.assertTrue(result["meets_min_content"])
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)

    def test_mcp_tool_integration(self):
        mcp = mcp_filing_server.create_server()
        self.assertIn("verify_compliance_document", mcp._tool_manager._tools)
