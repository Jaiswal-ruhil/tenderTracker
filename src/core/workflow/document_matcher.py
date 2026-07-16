"""
workflow/document_matcher.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Mixin: Firm document loading, exact/fuzzy matching, AI similarity scoring,
COMMON/category folder integration, and auto-pull from remembered paths.
"""
import os
import shutil
from difflib import SequenceMatcher
from typing import Dict, List

import db


class DocumentMatcherMixin:
    """Methods for matching required documents with available firm documents."""

    # ------------------------------------------------------------------ #
    # Firm document loading                                                #
    # ------------------------------------------------------------------ #

    def _get_firm_documents(self, firm_name: str = None) -> Dict:
        """
        Get firm documents from settings.

        Args:
            firm_name: Optional firm name to filter by.

        Returns:
            Dictionary mapping document keys to file paths.
        """
        settings = db.load_settings()
        firms = settings.get('firms', [])

        target_firm = None
        if firm_name:
            for firm in firms:
                if firm.get('name') == firm_name:
                    target_firm = firm
                    break

        # If no specific firm or not found, use first firm
        if not target_firm and firms:
            target_firm = firms[0]

        if target_firm:
            return target_firm.get('documents', {})

        return {}

    # ------------------------------------------------------------------ #
    # Similarity scoring                                                   #
    # ------------------------------------------------------------------ #

    def _calculate_similarity_score(self, text1: str, text2: str) -> float:
        """
        Calculate similarity score between two text strings using multiple methods.

        Returns:
            Similarity score between 0.0 and 1.0.
        """
        # Method 1: Sequence matching
        seq_score = SequenceMatcher(None, text1, text2).ratio()

        # Method 2: Word overlap
        words1 = set(text1.split())
        words2 = set(text2.split())
        if words1 or words2:
            overlap_score = len(words1 & words2) / len(words1 | words2)
        else:
            overlap_score = 0.0

        # Method 3: Substring matching
        substring_score = 0.0
        if text1 in text2 or text2 in text1:
            substring_score = 0.8

        # Combine scores with weights
        return (seq_score * 0.4) + (overlap_score * 0.4) + (substring_score * 0.2)

    # ------------------------------------------------------------------ #
    # AI-enhanced matching                                                 #
    # ------------------------------------------------------------------ #

    def _ai_enhanced_document_matching(self, required_docs: List[Dict], firm_documents: Dict) -> Dict:
        """
        Enhanced document matching using AI-powered similarity scoring.

        Returns:
            Enhanced matched documents dictionary with confidence scores.
        """
        enhanced_matches = {}

        for req_doc in required_docs:
            doc_name = req_doc.get('name', '').lower()
            best_match = None
            best_score = 0.0

            for firm_doc_name, firm_doc_path in firm_documents.items():
                if not isinstance(firm_doc_path, str):
                    continue
                firm_name_lower = firm_doc_name.lower()

                # Exact match
                if doc_name == firm_name_lower:
                    best_match = firm_doc_path
                    best_score = 1.0
                    break

                score = self._calculate_similarity_score(doc_name, firm_name_lower)
                if score > best_score and score > 0.6:  # Threshold for matching
                    best_match = firm_doc_path
                    best_score = score

            if best_match:
                enhanced_matches[req_doc['name']] = {
                    'path': best_match,
                    'confidence': best_score,
                    'source': 'firm'
                }

        return enhanced_matches

    # ------------------------------------------------------------------ #
    # Full matching (exact + fuzzy + COMMON + category folder)            #
    # ------------------------------------------------------------------ #

    def _match_documents(self, firm_documents: Dict):
        """
        Match required documents with available firm documents, COMMON folder
        files, and category-specific folder files.

        Side effects:
            - Populates self.matched_documents
            - Populates self.missing_documents
        """
        self.matched_documents = {}
        self.missing_documents = []

        type_mappings = {
            'gst': ['gst', 'gst certificate', 'gst registration'],
            'pan': ['pan', 'pan card'],
            'msme': ['msme', 'msme certificate', 'udyam'],
            'itr': ['itr', 'income tax', 'income tax return'],
            'bs': ['balance sheet', 'balance sheet'],
            'turnover': ['turnover', 'turnover certificate'],
            'experience': ['experience', 'experience proof', 'experience certificate'],
            'aadhaar': ['aadhaar', 'aadhar', 'aadhaar card', 'aadhar card'],
            'shareholder': ['shareholder', 'shareholder pattern'],
        }

        # Add COMMON folder files
        common_folder_path = os.path.join(self.filing_folder, '..', 'COMMON')
        common_documents = {}
        if os.path.exists(common_folder_path) and os.path.isdir(common_folder_path):
            for item in os.listdir(common_folder_path):
                item_path = os.path.join(common_folder_path, item)
                if os.path.isfile(item_path):
                    common_documents[item] = item_path
            if common_documents:
                self._log('info', f'Using {len(common_documents)} COMMON folder files for document matching')

        # Add Category subfolder files
        category_documents = {}
        category = getattr(self, 'category', '')
        if category and category != 'General':
            base_folder = os.path.join(self.filing_folder, '..')
            category_folder_path = ""
            if os.path.exists(base_folder) and os.path.isdir(base_folder):
                for item in os.listdir(base_folder):
                    item_path = os.path.join(base_folder, item)
                    if os.path.isdir(item_path) and item.lower() == category.lower():
                        category_folder_path = item_path
                        break
            if category_folder_path and os.path.exists(category_folder_path) and os.path.isdir(category_folder_path):
                for item in os.listdir(category_folder_path):
                    item_path = os.path.join(category_folder_path, item)
                    if os.path.isfile(item_path):
                        category_documents[item] = item_path
                if category_documents:
                    self._log('info', f"Using {len(category_documents)} category-specific files from '{os.path.basename(category_folder_path)}' folder")

        all_documents = {**firm_documents, **common_documents, **category_documents}

        for req_doc in self.required_documents:
            req_name_lower = req_doc['name'].lower()
            matched = False

            # Exact matches first
            for doc_key, doc_path in all_documents.items():
                if doc_path and isinstance(doc_path, str) and os.path.exists(doc_path):
                    doc_key_lower = doc_key.lower()
                    if req_name_lower in doc_key_lower or doc_key_lower in req_name_lower:
                        if doc_key in common_documents:
                            source = 'COMMON'
                        elif doc_key in category_documents:
                            source = f'Category ({category})'
                        else:
                            source = doc_key
                        self.matched_documents[req_doc['name']] = {
                            'path': doc_path,
                            'source': source,
                            'document': req_doc
                        }
                        matched = True
                        break

            # Fuzzy matches
            if not matched:
                for doc_key, doc_path in all_documents.items():
                    if doc_path and isinstance(doc_path, str) and os.path.exists(doc_path):
                        for map_type, keywords in type_mappings.items():
                            if any(kw in req_name_lower for kw in keywords) and map_type in doc_key.lower():
                                if doc_key in common_documents:
                                    source = 'COMMON'
                                elif doc_key in category_documents:
                                    source = f'Category ({category})'
                                else:
                                    source = doc_key
                                self.matched_documents[req_doc['name']] = {
                                    'path': doc_path,
                                    'source': source,
                                    'document': req_doc
                                }
                                matched = True
                                break
                    if matched:
                        break

            if not matched:
                self.missing_documents.append(req_doc)

    # ------------------------------------------------------------------ #
    # Category-specific helpers                                            #
    # ------------------------------------------------------------------ #

    def _is_category_specific_doc(self, doc_name: str) -> bool:
        """Check if a document is category-specific (not a standard firm document)."""
        standard_names = [
            "gst", "pan", "msme", "itr", "balance sheet",
            "turnover certificate", "shareholder pattern", "experience certificate"
        ]
        doc_lower = doc_name.lower()
        return not any(std in doc_lower for std in standard_names)

    def _auto_pull_category_documents(self, firm_name: str, category: str):
        """Auto-pull category-specific documents from last remembered locations."""
        settings = db.load_settings()
        firm_cat_docs = settings.get("firm_category_docs", {})
        saved_docs = firm_cat_docs.get(firm_name, {}).get(category, {})

        still_missing = []
        for doc in self.missing_documents:
            doc_name = doc['name']
            if self._is_category_specific_doc(doc_name):
                saved_path = saved_docs.get(doc_name)
                if saved_path and os.path.exists(saved_path):
                    dest_folder = os.path.join(self.filing_folder, "Category_Specific_Documents")
                    os.makedirs(dest_folder, exist_ok=True)
                    filename = os.path.basename(saved_path)
                    dest_path = os.path.join(dest_folder, filename)
                    try:
                        shutil.copy2(saved_path, dest_path)
                        self.matched_documents[doc_name] = {
                            'path': dest_path,
                            'source': 'auto-pull (remembered)',
                            'document': doc
                        }
                        self._log('ok', f"[Auto-pull] Found and copied remembered category document '{doc_name}': {filename}")
                    except Exception as e:
                        self._log('warn', f"Failed to auto-pull remembered document '{doc_name}': {e}")
                        still_missing.append(doc)
                else:
                    still_missing.append(doc)
            else:
                still_missing.append(doc)

        self.missing_documents = still_missing
