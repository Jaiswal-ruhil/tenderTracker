import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'core')))

import pdf_tools


class TestPdfTools(unittest.TestCase):
    def test_stirling_pdf_online_check(self):
        # Should return boolean without raising exception
        status = pdf_tools.is_stirling_pdf_online()
        self.assertIsInstance(status, bool)

    def test_merge_and_split_pdf(self):
        import fitz
        tmp_dir = os.path.join(os.path.dirname(__file__), 'tmp_pdf_test')
        os.makedirs(tmp_dir, exist_ok=True)
        pdf1 = os.path.join(tmp_dir, 'pdf1.pdf')
        pdf2 = os.path.join(tmp_dir, 'pdf2.pdf')
        merged = os.path.join(tmp_dir, 'merged.pdf')

        # Create dummy PDF 1
        d1 = fitz.open()
        p1 = d1.new_page()
        p1.insert_text((50, 50), "PDF 1 Page")
        d1.save(pdf1)
        d1.close()

        # Create dummy PDF 2
        d2 = fitz.open()
        p2 = d2.new_page()
        p2.insert_text((50, 50), "PDF 2 Page")
        d2.save(pdf2)
        d2.close()

        # Test merge
        success, out_path = pdf_tools.merge_pdfs([pdf1, pdf2], merged)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(out_path))

        # Test split
        split_dir = os.path.join(tmp_dir, 'split')
        pages = pdf_tools.split_pdf(merged, split_dir)
        self.assertEqual(len(pages), 2)

        # Cleanup
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)
