"""
document_verification_agent.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Agent to verify compliance documents (GST, PAN, MII local content, undertakings, experience proofs)
against expected firm metadata and tender requirements.
"""

import os
import re
from typing import Dict, Any, List, Optional
import pypdf
import db
import pdf_extractor

class DocumentVerificationAgent:
    """Verifies compliance documents for GeM bid submission compatibility."""
    
    def __init__(self):
        pass
        
    def _extract_text(self, file_path: str) -> str:
        """Safely extracts text from a PDF or plain text file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.pdf':
            try:
                with open(file_path, 'rb') as f:
                    return pdf_extractor.extract_text(f.read())
            except Exception as e:
                # Fallback to direct pypdf extraction if pdf_extractor fails
                try:
                    with open(file_path, 'rb') as f:
                        reader = pypdf.PdfReader(f)
                        text = []
                        for page in reader.pages:
                            text.append(page.extract_text() or "")
                        return "\n".join(text)
                except Exception as pypdf_err:
                    raise IOError(f"Failed to extract text from PDF: {pypdf_err}")
        elif ext in ['.txt', '.html', '.xml']:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        else:
            # For .doc/.docx, we check if python-docx is available, otherwise read binary as basic fallback
            if ext == '.docx':
                try:
                    import docx
                    doc = docx.Document(file_path)
                    return "\n".join([p.text for p in doc.paragraphs])
                except ImportError:
                    pass
            # Raw fallback
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()

    def verify_gst_certificate(self, file_path: str, expected_gstin: Optional[str] = None, expected_firm_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Verifies GST Certificate.
        Checks for valid GSTIN format, matching GSTIN number, and firm name presence.
        """
        try:
            text = self._extract_text(file_path)
        except Exception as e:
            return {"valid": False, "errors": [f"Text extraction failed: {e}"], "warnings": []}
            
        result = {
            "valid": True,
            "detected_gstins": [],
            "gstin_match": False,
            "firm_name_match": False,
            "errors": [],
            "warnings": []
        }
        
        # Regex for GSTIN (15 characters: 2 state digits, 10 PAN letters/digits, 1 entity code, 1 Z, 1 checksum)
        gstin_pattern = r'\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Zz]{1}[A-Z\d]{1}\b'
        detected = re.findall(gstin_pattern, text)
        result["detected_gstins"] = list(set(detected))
        
        if not result["detected_gstins"]:
            result["errors"].append("No valid GSTIN pattern detected in the document")
            result["valid"] = False
        else:
            if expected_gstin:
                clean_expected = expected_gstin.strip().upper()
                if any(clean_expected in g.upper() for g in result["detected_gstins"]):
                    result["gstin_match"] = True
                else:
                    result["errors"].append(f"Expected GSTIN '{clean_expected}' not found. Detected: {result['detected_gstins']}")
                    result["valid"] = False
            else:
                result["warnings"].append("No expected GSTIN provided for validation")
                
        # Check expected firm name
        if expected_firm_name:
            clean_firm = expected_firm_name.strip().lower()
            # Normalize spaces
            normalized_text = " ".join(text.lower().split())
            normalized_firm = " ".join(clean_firm.split())
            if normalized_firm in normalized_text:
                result["firm_name_match"] = True
            else:
                result["warnings"].append(f"Expected firm name '{expected_firm_name}' not found in document text")
                
        # Check signature or stamp keyword presence
        sig_keywords = ["signature", "signed", "seal", "stamp", "digitally signed", "esign"]
        if not any(k in text.lower() for k in sig_keywords):
            result["warnings"].append("No signature or official seal indicators detected in the document")
            
        return result

    def verify_pan_card(self, file_path: str, expected_pan: Optional[str] = None, expected_firm_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Verifies PAN Card.
        Checks for valid PAN format (10 characters: 5 letters, 4 digits, 1 letter) and matches PAN number.
        """
        try:
            text = self._extract_text(file_path)
        except Exception as e:
            return {"valid": False, "errors": [f"Text extraction failed: {e}"], "warnings": []}
            
        result = {
            "valid": True,
            "detected_pans": [],
            "pan_match": False,
            "firm_name_match": False,
            "errors": [],
            "warnings": []
        }
        
        # Regex for PAN Card
        pan_pattern = r'\b[A-Z]{5}\d{4}[A-Z]{1}\b'
        detected = re.findall(pan_pattern, text.upper())
        result["detected_pans"] = list(set(detected))
        
        if not result["detected_pans"]:
            result["errors"].append("No valid PAN pattern detected in the document")
            result["valid"] = False
        else:
            if expected_pan:
                clean_expected = expected_pan.strip().upper()
                if any(clean_expected == p for p in result["detected_pans"]):
                    result["pan_match"] = True
                else:
                    result["errors"].append(f"Expected PAN '{clean_expected}' not found. Detected: {result['detected_pans']}")
                    result["valid"] = False
            else:
                result["warnings"].append("No expected PAN provided for validation")
                
        # Check expected firm name
        if expected_firm_name:
            clean_firm = expected_firm_name.strip().lower()
            normalized_text = " ".join(text.lower().split())
            normalized_firm = " ".join(clean_firm.split())
            if normalized_firm in normalized_text:
                result["firm_name_match"] = True
            else:
                result["warnings"].append(f"Expected name '{expected_firm_name}' not found in PAN document text")
                
        return result

    def verify_mii_certificate(self, file_path: str, expected_bid_no: Optional[str] = None, min_local_content: int = 50) -> Dict[str, Any]:
        """
        Verifies Make in India self-certificate.
        Checks for bid number reference and local content percentage declaration.
        """
        try:
            text = self._extract_text(file_path)
        except Exception as e:
            return {"valid": False, "errors": [f"Text extraction failed: {e}"], "warnings": []}
            
        result = {
            "valid": True,
            "bid_no_match": False,
            "local_content_declared": None,
            "meets_min_content": False,
            "errors": [],
            "warnings": []
        }
        
        # Search for bid number in text
        if expected_bid_no:
            # Standardize formatting (replace slashes, hyphens, etc.)
            clean_bid = re.sub(r'[^A-Za-z0-9]', '', expected_bid_no).lower()
            clean_text = re.sub(r'[^A-Za-z0-9]', '', text).lower()
            if clean_bid in clean_text:
                result["bid_no_match"] = True
            else:
                result["errors"].append(f"Document does not reference expected Bid Number '{expected_bid_no}'")
                result["valid"] = False
        else:
            result["warnings"].append("No expected Bid Number provided for cross-verification")
            
        # Search for local content percentage
        pct_patterns = [
            r'(\d+)\s*%\s*(?:of)?\s*(?:local|value)\s*(?:content|addition)',
            r'(?:local|value)\s*(?:content|addition)\s*(?:is|of)?\s*(\d+)\s*%',
            r'percentage\s*of\s*local\s*content\s*(?:is)?\s*(\d+)'
        ]
        
        detected_pct = None
        for pattern in pct_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                detected_pct = int(matches[0])
                break
                
        if detected_pct is None:
            # Fallback: find any number preceding '%' sign
            matches = re.findall(r'(\d+)\s*%', text)
            if matches:
                detected_pct = int(matches[0])
                
        if detected_pct is not None:
            result["local_content_declared"] = detected_pct
            if detected_pct >= min_local_content:
                result["meets_min_content"] = True
            else:
                result["errors"].append(
                    f"Declared local content ({detected_pct}%) is below the minimum required content of {min_local_content}%"
                )
                result["valid"] = False
        else:
            result["errors"].append("Could not extract Make in India local content percentage declaration")
            result["valid"] = False
            
        # Verify signature presence
        sig_keywords = ["signature", "signed", "seal", "stamp", "representative", "deponent"]
        if not any(k in text.lower() for k in sig_keywords):
            result["warnings"].append("Make in India certificate lacks visible signature placeholder keywords")
            
        return result

    def verify_compliance_document(
        self,
        file_path: str,
        doc_type: str,
        expected_bid_no: Optional[str] = None,
        expected_firm_name: Optional[str] = None,
        expected_gstin: Optional[str] = None,
        expected_pan: Optional[str] = None,
        min_local_content: int = 50
    ) -> Dict[str, Any]:
        """
        Unified verification entry point.
        Supported doc_types: 'gst', 'pan', 'mii_certificate', 'undertaking', 'affidavit'.
        """
        clean_type = doc_type.lower().strip()
        
        if not os.path.exists(file_path):
            return {"valid": False, "errors": [f"File does not exist: {file_path}"], "warnings": []}
            
        if clean_type == "gst":
            return self.verify_gst_certificate(file_path, expected_gstin, expected_firm_name)
        elif clean_type == "pan":
            return self.verify_pan_card(file_path, expected_pan, expected_firm_name)
        elif clean_type == "mii_certificate":
            return self.verify_mii_certificate(file_path, expected_bid_no, min_local_content)
        elif clean_type in ["undertaking", "affidavit", "bidder_undertaking"]:
            # General signature and bid number check for undertakings/affidavits
            try:
                text = self._extract_text(file_path)
            except Exception as e:
                return {"valid": False, "errors": [f"Text extraction failed: {e}"], "warnings": []}
                
            result = {"valid": True, "errors": [], "warnings": []}
            
            # Signature check
            sig_keywords = ["signature", "signed", "seal", "stamp", "representative", "deponent"]
            if not any(k in text.lower() for k in sig_keywords):
                result["warnings"].append("No signature keywords detected in the document")
                
            # Bid number reference check
            if expected_bid_no:
                clean_bid = re.sub(r'[^A-Za-z0-9]', '', expected_bid_no).lower()
                clean_text = re.sub(r'[^A-Za-z0-9]', '', text).lower()
                if clean_bid not in clean_text:
                    result["warnings"].append(f"Undertaking does not explicitly reference the expected Bid Number '{expected_bid_no}'")
                    
            return result
        else:
            # Basic file integrity check
            from filing_workflow import FilingWorkflow
            workflow = FilingWorkflow()
            return workflow._validate_document_integrity(file_path)
