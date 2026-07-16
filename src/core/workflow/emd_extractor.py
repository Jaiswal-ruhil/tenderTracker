"""
workflow/emd_extractor.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Mixin: Category identification and EMD/security-deposit extraction via LLM.
"""
import re
import json
from typing import Dict

import db
import llm


class EmdExtractorMixin:
    """Methods for identifying tender category and extracting EMD details."""

    def _identify_category_and_docs(self, combined_text: str, tender_record: Dict) -> str:
        """Identify the item category of the tender using the LLM."""
        items_str = tender_record.get('items', '') or tender_record.get('category', '') or ""
        excerpt = combined_text[:4000]

        prompt = f"""
Analyze the GeM tender details:
Items/Category: "{items_str}"

Text Excerpt:
{excerpt}

Identify a single high-level product/service category for this tender (e.g. "Cables", "IT Hardware", "Medical Equipment", "Furniture", "Office Supplies", "General Services", etc.).
Return ONLY the category name in 1-3 words (e.g. "Cables" or "IT Hardware"). No other text, no markdown.
"""
        try:
            settings = db.load_settings()
            provider = settings.get('llm_provider', 'local')
            api_key = settings.get('llm_api_key', '')
            base_url = settings.get('llm_base_url', '')
            model = settings.get('llm_model', '')

            if provider == 'Local LLM (LM Studio / Ollama)':
                self._local_llm_used = True
            res_str = llm.call_llm(prompt, provider, api_key, base_url, model, response_json=False)
            category = res_str.strip().strip('"').strip("'")
            if "</think>" in category:
                category = category.split("</think>")[-1].strip()

            category = category.replace("\n", " ")
            category = re.sub(r'\s+', ' ', category)
            if len(category) > 40:
                category = "General"
            return category
        except Exception as e:
            self._log('warn', f"Failed to identify category via LLM: {e}")
            return "General"

    def _extract_emd_details_llm(self, combined_text: str) -> Dict:
        """Call LLM to extract EMD/Security deposit details from combined text."""
        excerpt = combined_text[:12000]
        prompt = f"""
Analyze the following text from a GeM tender and extract Earnest Money Deposit (EMD) or Security Deposit / Performance Bank Guarantee (PBG) details.

TEXT:
{excerpt}

Return ONLY a JSON object (no markdown, no backticks, no thinking block) with the following structure:
{{
  "emd_required": true or false,
  "emd_amount": "amount in Rs. or 'Exempted' or 'N/A'",
  "emd_exemption_allowed": true or false,
  "pbg_required": true or false,
  "pbg_percent": "percentage or amount or 'N/A'",
  "details_summary": "Brief summary of EMD/PBG instructions and bank details if any"
}}
"""
        try:
            settings = db.load_settings()
            provider = settings.get('llm_provider', 'local')
            api_key = settings.get('llm_api_key', '')
            base_url = settings.get('llm_base_url', '')
            model = settings.get('llm_model', '')

            if provider == 'Local LLM (LM Studio / Ollama)':
                self._local_llm_used = True
            res_str = llm.call_llm(prompt, provider, api_key, base_url, model, response_json=True)
            if "</think>" in res_str:
                res_str = res_str.split("</think>")[-1].strip()

            cleaned_json = llm.clean_json_response(res_str)
            return json.loads(cleaned_json)
        except Exception as e:
            self._log('warn', f"Failed to parse EMD details via LLM: {e}")
            return {
                "emd_required": False,
                "emd_amount": "N/A",
                "emd_exemption_allowed": False,
                "pbg_required": False,
                "pbg_percent": "N/A",
                "details_summary": "Failed to extract EMD details."
            }
