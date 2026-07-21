"""
workflow/document_matcher.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Mixin: Firm document loading, exact/fuzzy matching, AI similarity scoring,
COMMON/category folder integration, and auto-pull from remembered paths.
"""
import os
import re
import shutil
from datetime import datetime, date
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

import db


class DocumentMatcherMixin:
    """Methods for matching required documents with available firm documents."""

    # ------------------------------------------------------------------ #
    # Firm document loading & Expiration                                   #
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

    def _get_firm_expiries(self, firm_name: str = None) -> Dict:
        """
        Get firm document expiries from settings.

        Args:
            firm_name: Optional firm name to filter by.

        Returns:
            Dictionary mapping document keys to expiry date strings (YYYY-MM-DD).
        """
        settings = db.load_settings()
        firms = settings.get('firms', [])

        target_firm = None
        if firm_name:
            for firm in firms:
                if firm.get('name') == firm_name:
                    target_firm = firm
                    break

        if not target_firm and firms:
            target_firm = firms[0]

        if target_firm:
            return target_firm.get('expiries', {})

        return {}

    def _check_document_expiration(self, doc_path: str, expiry_date_str: Optional[str] = None) -> Dict:
        """
        Check whether a document is valid, expiring soon (<= 30 days), or expired.

        Args:
            doc_path: File path of the document.
            expiry_date_str: Optional expiry date string (YYYY-MM-DD, DD-MM-YYYY, YYYY/MM/DD).

        Returns:
            Dict containing 'expiry_date', 'status', 'is_expired', 'expiring_soon', 'days_remaining'.
        """
        parsed_date = None
        raw_str = expiry_date_str or ""

        # If no explicit expiry provided, check if embedded in filename
        if not raw_str and doc_path:
            filename = os.path.basename(doc_path)
            match = re.search(
                r'(?:exp|expiry|valid|till)[_\-\s]*(\d{4}[_\-\/]\d{2}[_\-\/]\d{2}|\d{2}[_\-\/]\d{2}[_\-\/]\d{4})',
                filename, re.I
            )
            if not match:
                match = re.search(r'(\d{4}[_\-\/]\d{2}[_\-\/]\d{2})', filename)
            if match:
                raw_str = match.group(1)

        if raw_str:
            clean_str = raw_str.strip().replace('/', '-')
            formats = ["%Y-%m-%d", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S"]
            for fmt in formats:
                try:
                    parsed_date = datetime.strptime(clean_str, fmt).date()
                    break
                except ValueError:
                    pass

        if not parsed_date:
            return {
                'expiry_date': raw_str or None,
                'status': 'UNKNOWN',
                'is_expired': False,
                'expiring_soon': False,
                'days_remaining': None
            }

        today = date.today()
        days_rem = (parsed_date - today).days

        if days_rem < 0:
            status = 'EXPIRED'
            is_expired = True
            expiring_soon = False
        elif days_rem <= 30:
            status = 'EXPIRING_SOON'
            is_expired = False
            expiring_soon = True
        else:
            status = 'VALID'
            is_expired = False
            expiring_soon = False

        return {
            'expiry_date': parsed_date.strftime('%Y-%m-%d'),
            'status': status,
            'is_expired': is_expired,
            'expiring_soon': expiring_soon,
            'days_remaining': days_rem
        }

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

    # ------------------------------------------------------------------ #
    # AI-enhanced matching                                                 #
    # ------------------------------------------------------------------ #

    def _ai_enhanced_document_matching(self, required_docs: List[Dict], firm_documents: Dict) -> Dict:
        """
        Enhanced document matching using AI-powered similarity scoring and alias mapping.
        Includes firm documents, COMMON folder documents, and Category-specific documents.

        Returns:
            Enhanced matched documents dictionary with confidence scores.
        """
        # Gather all candidate documents (firm + COMMON + category)
        common_documents = {}
        if hasattr(self, 'filing_folder') and self.filing_folder:
            common_folder_path = os.path.normpath(os.path.join(self.filing_folder, '..', 'COMMON'))
            if os.path.exists(common_folder_path):
                try:
                    for item in os.listdir(common_folder_path):
                        item_path = os.path.normpath(os.path.join(common_folder_path, item))
                        if item.endswith(('.pdf', '.doc', '.docx', '.jpg', '.png', '.txt')) or not os.path.isdir(item_path):
                            common_documents[item] = item_path
                except Exception:
                    pass

        category_documents = {}
        category = getattr(self, 'category', '')
        if category and category != 'General' and hasattr(self, 'filing_folder') and self.filing_folder:
            category_folder_path = self._find_category_folder(self.filing_folder, category)
            if category_folder_path and os.path.exists(category_folder_path):
                try:
                    for item in os.listdir(category_folder_path):
                        item_path = os.path.normpath(os.path.join(category_folder_path, item))
                        if item.endswith(('.pdf', '.doc', '.docx', '.jpg', '.png', '.txt')) or not os.path.isdir(item_path):
                            category_documents[item] = item_path
                except Exception:
                    pass

        all_documents = {**firm_documents, **common_documents, **category_documents}
        enhanced_matches = {}
        used_paths = set()

        # Alias dictionary for GeM document titles
        alias_map = {
            "experience": ["experience criteria", "experience", "past experience", "work experience", "work order", "po", "purchase order", "order", "contract"],
            "past_performance": ["past performance", "performance criteria", "performance statement", "performance certificate", "performance", "completion certificate", "execution certificate"],
            "turnover": ["bidder turnover", "turnover criteria", "turnover", "annual turnover", "turnover certificate", "ca turnover", "balance sheet", "itr", "audited accounts"],
            "oem": ["oem authorization", "oem certificate", "maf", "manufacturer authorization", "oem declaration", "oem"],
            "emd": ["emd", "earnest money", "bid security", "emd exemption", "emd receipt", "bank guarantee", "solvency"],
            "compliance": ["compliance", "technical compliance", "compliance statement", "specification compliance", "datasheet", "specification sheet"],
            "border": ["land border", "clause 144", "border declaration", "rule 144"],
            "blacklisting": ["blacklisting", "non blacklisting", "debarment", "non-blacklisting", "affidavit", "undertaking"],
            "net_worth": ["net worth", "networth", "financial standing", "ca net worth"],
            "atc": ["additional doc", "requested in atc", "atc", "additional document", "mii", "local content", "oem authorization", "undertaking", "declaration", "affidavit", "compliance"]
        }

        for req_doc in required_docs:
            doc_name = req_doc.get('name', '').lower().replace('_', ' ').replace('-', ' ')
            best_match = None
            best_score = 0.0
            best_source = 'firm'

            for doc_key, doc_path in all_documents.items():
                if not isinstance(doc_path, str) or doc_path in used_paths:
                    continue

                file_name = os.path.splitext(os.path.basename(doc_path))[0]
                clean_key = f"{doc_key} {file_name}".lower().replace('_', ' ').replace('-', ' ')

                # 1. Exact or substring match
                if doc_name in clean_key or clean_key in doc_name:
                    best_match = doc_path
                    best_score = 0.95
                    best_source = 'COMMON' if doc_key in common_documents else (f'Category ({category})' if doc_key in category_documents else doc_key)
                    break

                # 2. Alias match
                for cat_key, aliases in alias_map.items():
                    if any(alias in doc_name for alias in aliases):
                        if cat_key in clean_key or any(alias in clean_key for alias in aliases):
                            score = 0.88
                            if score > best_score:
                                best_score = score
                                best_match = doc_path
                                best_source = 'COMMON' if doc_key in common_documents else (f'Category ({category})' if doc_key in category_documents else doc_key)

                # 3. Fuzzy ratio match
                score = self._calculate_similarity_score(doc_name, clean_key)
                if score > best_score and score > 0.55:
                    best_match = doc_path
                    best_score = score
                    best_source = 'COMMON' if doc_key in common_documents else (f'Category ({category})' if doc_key in category_documents else doc_key)

            if best_match:
                used_paths.add(best_match)
                enhanced_matches[req_doc['name']] = {
                    'path': best_match,
                    'confidence': round(best_score, 2),
                    'source': best_source,
                    'document': req_doc
                }

        return enhanced_matches

    def _find_category_folder(self, filing_folder: str, category: str, base_dir: str = "") -> Optional[str]:
        """Find matching category subfolder (e.g. 'Cable', 'Cables', 'Cable Documents')."""
        if not category or category in ('General', 'N/A'):
            return None

        cat_clean = category.strip().lower()
        search_dirs = []
        if filing_folder:
            search_dirs.append(os.path.normpath(os.path.join(filing_folder, '..')))
            search_dirs.append(os.path.normpath(os.path.join(filing_folder, '..', '..')))
            search_dirs.append(os.path.normpath(os.path.join(filing_folder, '..', 'COMMON')))
        if base_dir:
            search_dirs.append(os.path.normpath(base_dir))
            search_dirs.append(os.path.normpath(os.path.join(base_dir, 'COMMON')))

        seen = set()
        # 1. Exact or plural match
        for p_dir in search_dirs:
            if not p_dir or p_dir in seen or not os.path.exists(p_dir) or not os.path.isdir(p_dir):
                continue
            seen.add(p_dir)
            try:
                for item in os.listdir(p_dir):
                    item_path = os.path.join(p_dir, item)
                    if os.path.isdir(item_path):
                        item_clean = item.strip().lower()
                        if (item_clean == cat_clean or
                            item_clean == cat_clean + 's' or
                            cat_clean == item_clean + 's'):
                            return item_path
            except Exception:
                pass

        # 2. Substring match
        seen.clear()
        for p_dir in search_dirs:
            if not p_dir or p_dir in seen or not os.path.exists(p_dir) or not os.path.isdir(p_dir):
                continue
            seen.add(p_dir)
            try:
                for item in os.listdir(p_dir):
                    item_path = os.path.join(p_dir, item)
                    if os.path.isdir(item_path) and item.upper() != "COMMON":
                        item_clean = item.strip().lower()
                        if cat_clean in item_clean or item_clean in cat_clean:
                            return item_path
            except Exception:
                pass

        return None

    # ------------------------------------------------------------------ #
    # Full matching (exact + fuzzy + COMMON + category folder)            #
    # ------------------------------------------------------------------ #

    def _match_documents(self, firm_documents: Dict, firm_expiries: Dict = None):
        """
        Match required documents with available firm documents, COMMON folder
        files, and category-specific folder files. Evaluates expiration dates.

        Side effects:
            - Populates self.matched_documents
            - Populates self.missing_documents
        """
        self.matched_documents = {}
        self.missing_documents = []

        if firm_expiries is None:
            firm_name = getattr(self, 'firm_name', '')
            firm_expiries = self._get_firm_expiries(firm_name)

        type_mappings = {
            'gst': ['gst', 'gstin', 'gst certificate', 'gst registration', 'goods and services tax'],
            'pan': ['pan', 'pan card', 'pan certificate', 'permanent account number'],
            'msme': ['msme', 'msme certificate', 'udyam', 'udyam registration', 'startup', 'nsic', 'ssi'],
            'itr': ['itr', 'income tax', 'income tax return', 'itr 1', 'itr 2', 'itr 3', 'itr_1', 'itr_2', 'itr_3', 'itr-v'],
            'bs': ['balance sheet', 'bs', 'balance_sheet', 'bs_1', 'bs_2', 'bs_3', 'profit loss', 'audited accounts'],
            'turnover': ['turnover', 'bidder turnover', 'turnover criteria', 'annual turnover', 'turnover certificate', 'ca turnover', 'ca cert', 'ca certificate'],
            'experience': ['experience', 'experience criteria', 'past experience', 'work experience', 'experience proof', 'experience certificate', 'work order', 'po', 'purchase order', 'order', 'contract'],
            'past_performance': ['past performance', 'performance criteria', 'performance statement', 'performance certificate', 'performance', 'past_performance', 'completion certificate', 'execution certificate'],
            'oem': ['oem', 'oem authorization', 'oem certificate', 'maf', 'manufacturer authorization', 'oem declaration'],
            'emd': ['emd', 'earnest money', 'bid security', 'emd exemption', 'emd receipt', 'bank guarantee', 'solvency'],
            'compliance': ['compliance', 'technical compliance', 'compliance statement', 'specification compliance', 'datasheet', 'specification sheet'],
            'border': ['land border', 'clause 144', 'border declaration', 'rule 144', 'land border sharing'],
            'blacklisting': ['blacklisting', 'non blacklisting', 'debarment', 'non-blacklisting', 'affidavit', 'undertaking'],
            'net_worth': ['net worth', 'networth', 'financial standing', 'ca net worth'],
            'atc': ['additional doc', 'requested in atc', 'atc', 'additional document', 'atc document', 'mii declaration', 'local content', 'oem authorization', 'undertaking', 'declaration', 'affidavit', 'compliance'],
            'aadhaar': ['aadhaar', 'aadhar', 'aadhaar card', 'aadhar card'],
            'shareholder': ['shareholder', 'shareholder pattern', 'shareholding'],
        }

        # Add COMMON folder files
        common_folder_path = os.path.join(self.filing_folder, '..', 'COMMON') if hasattr(self, 'filing_folder') and self.filing_folder else ""
        common_documents = {}
        if common_folder_path and os.path.exists(common_folder_path) and os.path.isdir(common_folder_path):
            for item in os.listdir(common_folder_path):
                item_path = os.path.join(common_folder_path, item)
                if os.path.isfile(item_path):
                    common_documents[item] = item_path
            if common_documents and hasattr(self, '_log'):
                self._log('info', f'Using {len(common_documents)} COMMON folder files for document matching')

        # Add Category subfolder files
        category_documents = {}
        category = getattr(self, 'category', '')
        if category and category != 'General' and hasattr(self, 'filing_folder') and self.filing_folder:
            category_folder_path = self._find_category_folder(self.filing_folder, category)
            if category_folder_path and os.path.exists(category_folder_path) and os.path.isdir(category_folder_path):
                for item in os.listdir(category_folder_path):
                    item_path = os.path.join(category_folder_path, item)
                    if os.path.isfile(item_path):
                        category_documents[item] = item_path
                if category_documents and hasattr(self, '_log'):
                    self._log('info', f"Using {len(category_documents)} category-specific files from '{os.path.basename(category_folder_path)}' folder")

        all_documents = {**firm_documents, **common_documents, **category_documents}
        used_paths = set()

        for req_doc in self.required_documents:
            req_name_clean = req_doc['name'].lower().replace('_', ' ').replace('-', ' ')
            matched = False

            # Exact or Substring matches first
            for doc_key, doc_path in all_documents.items():
                if doc_path and isinstance(doc_path, str) and os.path.exists(doc_path) and doc_path not in used_paths:
                    doc_key_clean = os.path.splitext(os.path.basename(doc_key))[0].lower().replace('_', ' ').replace('-', ' ')
                    if req_name_clean in doc_key_clean or doc_key_clean in req_name_clean:
                        if doc_key in common_documents:
                            source = 'COMMON'
                        elif doc_key in category_documents:
                            source = f'Category ({category})'
                        else:
                            source = doc_key
                        
                        expiry_info = self._check_document_expiration(doc_path, firm_expiries.get(doc_key))
                        self.matched_documents[req_doc['name']] = {
                            'path': doc_path,
                            'source': source,
                            'document': req_doc,
                            'expiry_date': expiry_info.get('expiry_date'),
                            'status': expiry_info.get('status', 'UNKNOWN'),
                            'is_expired': expiry_info.get('is_expired', False),
                            'expiring_soon': expiry_info.get('expiring_soon', False),
                            'days_remaining': expiry_info.get('days_remaining'),
                        }
                        used_paths.add(doc_path)
                        matched = True

                        if expiry_info.get('is_expired'):
                            if hasattr(self, '_log'):
                                self._log('warn', f"[Document Match] WARNING: Matched '{req_doc['name']}' ({os.path.basename(doc_path)}) is EXPIRED (Expiry: {expiry_info['expiry_date']})!")
                        elif expiry_info.get('expiring_soon'):
                            if hasattr(self, '_log'):
                                self._log('warn', f"[Document Match] NOTICE: Matched '{req_doc['name']}' ({os.path.basename(doc_path)}) EXPIRING SOON in {expiry_info['days_remaining']} days.")
                        break

            # Fuzzy matches
            if not matched:
                for map_type, keywords in type_mappings.items():
                    if any(kw in req_name_clean for kw in keywords):
                        for doc_key, doc_path in all_documents.items():
                            if doc_path and isinstance(doc_path, str) and os.path.exists(doc_path) and doc_path not in used_paths:
                                doc_key_clean = os.path.splitext(os.path.basename(doc_key))[0].lower().replace('_', ' ').replace('-', ' ')
                                if map_type in doc_key_clean or any(kw in doc_key_clean for kw in keywords):
                                    if doc_key in common_documents:
                                        source = 'COMMON'
                                    elif doc_key in category_documents:
                                        source = f'Category ({category})'
                                    else:
                                        source = doc_key

                                    expiry_info = self._check_document_expiration(doc_path, firm_expiries.get(doc_key))
                                    self.matched_documents[req_doc['name']] = {
                                        'path': doc_path,
                                        'source': source,
                                        'document': req_doc,
                                        'expiry_date': expiry_info.get('expiry_date'),
                                        'status': expiry_info.get('status', 'UNKNOWN'),
                                        'is_expired': expiry_info.get('is_expired', False),
                                        'expiring_soon': expiry_info.get('expiring_soon', False),
                                        'days_remaining': expiry_info.get('days_remaining'),
                                    }
                                    used_paths.add(doc_path)
                                    matched = True

                                    if expiry_info.get('is_expired'):
                                        if hasattr(self, '_log'):
                                            self._log('warn', f"[Document Match] WARNING: Matched '{req_doc['name']}' ({os.path.basename(doc_path)}) is EXPIRED (Expiry: {expiry_info['expiry_date']})!")
                                    elif expiry_info.get('expiring_soon'):
                                        if hasattr(self, '_log'):
                                            self._log('warn', f"[Document Match] NOTICE: Matched '{req_doc['name']}' ({os.path.basename(doc_path)}) EXPIRING SOON in {expiry_info['days_remaining']} days.")
                                    break
                            if matched:
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
