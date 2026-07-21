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

    def test_collect_and_prepare_upload_package(self):
        import fitz, tempfile, shutil
        tmp_dir = tempfile.mkdtemp()
        try:
            pdf1 = os.path.join(tmp_dir, 'exp1.pdf')
            pdf2 = os.path.join(tmp_dir, 'exp2.pdf')
            d1 = fitz.open(); p1 = d1.new_page(); p1.insert_text((50,50), "Exp 1"); d1.save(pdf1); d1.close()
            d2 = fitz.open(); p2 = d2.new_page(); p2.insert_text((50,50), "Exp 2"); d2.save(pdf2); d2.close()

            req_docs = [{'name': 'Additional Doc 1 (Requested in ATC): Proof of 3 Years Experience'}]
            matched_docs = {'Additional Doc 1 (Requested in ATC): Proof of 3 Years Experience': [pdf1, pdf2]}
            
            res = self.agent.collect_and_prepare_upload_package(req_docs, matched_docs, {}, tmp_dir)
            self.assertTrue(res['success'])
            self.assertEqual(res['collected_count'], 1)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
