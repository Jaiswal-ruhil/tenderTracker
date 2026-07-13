import os
import sys
import unittest
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'core')))

import template_generator
import mcp_filing_server


class TestTemplateGenerator(unittest.TestCase):
    def test_render_template_basic(self):
        template = "Hello {firm_name}, your bid is {bid_no}."
        context = {"firm_name": "Test Firm Ltd.", "bid_no": "GEM/2026/B/123"}
        result = template_generator.render_template(template, context)
        self.assertEqual(result, "Hello Test Firm Ltd., your bid is GEM/2026/B/123.")

    def test_render_template_defaults(self):
        template = "{firm_name} - {category} - {bid_no}"
        context = {}  # Empty context, should use defaults
        result = template_generator.render_template(template, context)
        self.assertIn("Unnamed Firm", result)
        self.assertIn("General", result)
        self.assertIn("N/A", result)

    def test_generate_document_all_types_html_fallback(self):
        types = ["bidder_undertaking", "declaration", "affidavit", "mii_certificate"]
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict('sys.modules', {'weasyprint': None, 'pdfkit': None}):
                for t in types:
                    context = {
                        "bid_no": "GEM/2026/B/9520877",
                        "firm_name": "Acme Corp",
                        "category": "Office Equipment",
                        "local_content_percentage": "60",
                        "local_content_location": "Delhi factory"
                    }
                    success, path, warning = template_generator.generate_document(
                        tmpdir, t, context
                    )
                    
                    self.assertTrue(success)
                    self.assertTrue(path.endswith(f"{t}.html"))
                    self.assertIsNotNone(warning)
                    self.assertTrue(os.path.exists(path))
                    
                    # Verify key replacements in generated HTML
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                        self.assertIn("GEM/2026/B/9520877", content)
                        self.assertIn("Acme Corp", content)
                        if t == "mii_certificate":
                            self.assertIn("60%", content)
                            self.assertIn("Delhi factory", content)

    def test_mcp_tool_integration(self):
        mcp = mcp_filing_server.create_server()
        self.assertIn("generate_templated_document", mcp._tool_manager._tools)
