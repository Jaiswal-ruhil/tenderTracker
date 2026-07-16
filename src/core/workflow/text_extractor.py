"""
workflow/text_extractor.py
~~~~~~~~~~~~~~~~~~~~~~~~~~
Mixin: Text extraction from PDFs, Excel, CSV; regex and LLM document requirement
extraction; GeM seller document requirement extraction.
"""
import json
import re
from typing import Dict, List, Optional

import db
import llm
import pdf_extractor


class TextExtractorMixin:
    """Methods for extracting text and document requirements from tender files."""

    # ------------------------------------------------------------------ #
    # Text extraction                                                      #
    # ------------------------------------------------------------------ #

    def _extract_pdf_text(self, pdf_path: str) -> Optional[str]:
        """Extract text from a PDF file."""
        try:
            with open(pdf_path, 'rb') as f:
                pdf_bytes = f.read()

            pdf_text = pdf_extractor.extract_text(pdf_bytes)
            if pdf_text:
                self._log('ok', f'Extracted {len(pdf_text)} characters from PDF')
                return pdf_text
            else:
                self._log('warn', 'PDF text extraction returned empty result')
                return None

        except Exception as e:
            self._log('err', f'PDF text extraction failed: {e}')
            return None

    def _extract_text_from_additional_files(self, folder_path: str) -> Dict[str, str]:
        """Extract text from all PDF, Excel, and CSV files in the folder."""
        files_text = {}
        if not folder_path or not __import__('os').path.exists(folder_path):
            return files_text

        import os

        for f in os.listdir(folder_path):
            f_path = os.path.join(folder_path, f)
            if not os.path.isfile(f_path):
                continue

            f_lower = f.lower()
            if f_lower.endswith('.pdf'):
                try:
                    with open(f_path, 'rb') as pdf_file:
                        pdf_bytes = pdf_file.read()
                    text = pdf_extractor.extract_text(pdf_bytes)
                    if text:
                        files_text[f] = text
                except Exception as e:
                    self._log('warn', f"Failed to extract text from additional PDF '{f}': {e}")
            elif f_lower.endswith(('.xlsx', '.xls')):
                try:
                    import openpyxl
                    wb = openpyxl.load_workbook(f_path, read_only=True, data_only=True)
                    text_parts = []
                    for sheet in wb.worksheets:
                        text_parts.append(f"--- Sheet: {sheet.title} ---")
                        for row in sheet.iter_rows(values_only=True):
                            row_str = " | ".join(str(cell) for cell in row if cell is not None)
                            if row_str.strip():
                                text_parts.append(row_str)
                    files_text[f] = "\n".join(text_parts)
                except Exception as e:
                    self._log('warn', f"Failed to extract text from additional Excel '{f}': {e}")
            elif f_lower.endswith('.csv'):
                try:
                    with open(f_path, 'r', encoding='utf-8', errors='ignore') as csv_file:
                        files_text[f] = f"--- CSV File: {f} ---\n" + csv_file.read()
                except Exception as e:
                    self._log('warn', f"Failed to extract text from additional CSV '{f}': {e}")

        return files_text

    # ------------------------------------------------------------------ #
    # Document requirement extraction                                      #
    # ------------------------------------------------------------------ #

    def _extract_required_documents(self, pdf_text: str) -> List[Dict]:
        """
        Extract required documents from PDF text using hybrid regex/LLM approach.

        Returns list of document requirement dicts:
        [{'name', 'description', 'category', 'required', 'source'}]
        """
        documents = []

        # Step 1: Regex patterns for common document types
        regex_docs = self._extract_documents_regex(pdf_text)
        documents.extend(regex_docs)

        # Step 2: LLM supplement (always run when provider is enabled)
        provider = db.load_settings().get('llm_provider', 'Disabled')
        if provider not in ('', 'Disabled', None):
            self._log('info', 'Supplementing regex results with LLM analysis...')
            llm_docs = self._extract_documents_llm(pdf_text)
            documents.extend(llm_docs)

        # Remove duplicates based on name
        seen_names = set()
        unique_docs = []
        for doc in documents:
            doc_name_lower = doc['name'].lower()
            if doc_name_lower not in seen_names:
                seen_names.add(doc_name_lower)
                unique_docs.append(doc)

        return unique_docs

    def _extract_documents_regex(self, pdf_text: str) -> List[Dict]:
        """Extract document requirements using regex patterns."""
        documents = []
        text_lower = pdf_text.lower()

        document_patterns = [
            (r'gst\s*(certificate|registration|registration\s*certificate)', 'GST Certificate', 'Financial'),
            (r'pan\s*(card|number)', 'PAN Card', 'Financial'),
            (r'aadh?a?r\s*(card|number)?', 'Aadhaar Card', 'Legal'),
            (r'msme\s*(certificate|registration|udyam\s*registration)', 'MSME Certificate', 'Legal'),
            (r'income\s*tax\s*return|itr', 'Income Tax Return (ITR)', 'Financial'),
            (r'balance\s*sheet', 'Balance Sheet', 'Financial'),
            (r'turnover\s*certificate', 'Turnover Certificate', 'Financial'),
            (r'shareholder\s*(pattern|details|certificate)', 'Shareholder Pattern', 'Legal'),
            (r'experience\s*certificate', 'Experience Certificate', 'Technical'),
            (r'oem\s*(authorization|certificate)', 'OEM Authorization', 'Technical'),
            (r'mii\s*(declaration|certificate|compliance)', 'MII Declaration', 'Technical'),
            (r'technical\s*specifications', 'Technical Specifications', 'Technical'),
            (r'annexure', 'Annexure', 'Technical'),
            (r'bid\s*security\s*deposit|emd', 'EMD Document', 'Financial'),
            (r'epbg\s*(document|certificate)', 'ePBG Document', 'Financial'),
        ]

        for pattern, name, category in document_patterns:
            if re.search(pattern, text_lower):
                documents.append({
                    'name': name,
                    'description': f'{name} as specified in tender document',
                    'category': category,
                    'required': True,
                    'source': 'regex'
                })

        number_words = {
            'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        }
        number_pattern = r'\d+|one|two|three|four|five|six|seven|eight|nine|ten'

        def normalized_number(value: str) -> str:
            return str(number_words.get(value, int(value))) if value.isdigit() else str(number_words[value])

        experience_patterns = [
            re.compile(
                rf'\b(?P<years>{number_pattern})\s*(?:-\s*)?(?:years?|yrs?)\s*(?:of\s+)?'
                r'(?:(?:past|similar)\s+)?experience(?:\s+(?:of|in|with)\s+(?P<scope>[^,;\n.]+?))?'
                r'(?=\s*(?:is|are|must|shall|will|and|,|;|\.|\\n|$))'
            ),
            re.compile(
                rf'\b(?:past\s+|similar\s+)?experience\s*(?:required)?\s*(?::|-|of|for|in)\s*'
                rf'(?P<years>{number_pattern})\s*(?:-\s*)?(?:years?|yrs?)'
                r'(?:\s+(?:of|in|with)\s+(?P<scope>[^,;\n.]+?))?'
                r'(?=\s*(?:is|are|must|shall|will|and|,|;|\.|\\n|$))'
            ),
        ]
        for pattern in experience_patterns:
            experience_match = pattern.search(text_lower)
            if not experience_match:
                continue
            years = normalized_number(experience_match.group('years'))
            scope = (experience_match.groupdict().get('scope') or '').strip()
            scope_description = f' of {scope}' if scope else ''
            documents.append({
                'name': f'Experience Proof - {years} Years',
                'description': (
                    f'Proof of {years} years of experience{scope_description} '
                    'as specified in tender document'
                ),
                'category': 'Technical',
                'required': True,
                'source': 'regex'
            })
            break

        turnover_patterns = [
            re.compile(
                rf'\b(?:last|previous|past)\s+(?P<period>{number_pattern})\s*(?:-\s*)?'
                r'(?:financial\s+)?years?\s+(?:turn\s*over|turnover)\b'
            ),
            re.compile(
                rf'\b(?:turn\s*over|turnover)\b[^.\n;]{{0,80}}?\b'
                rf'(?:last|previous|past)\s+(?P<period>{number_pattern})\s*(?:-\s*)?(?:financial\s+)?years?\b'
            ),
        ]
        for pattern in turnover_patterns:
            turnover_match = pattern.search(text_lower)
            if not turnover_match:
                continue
            period = normalized_number(turnover_match.group('period'))
            documents.append({
                'name': f'Turnover Proof - Last {period} Years',
                'description': (
                    f'Turnover proof for the last {period} years as specified '
                    'in tender document'
                ),
                'category': 'Financial',
                'required': True,
                'source': 'regex'
            })
            break

        year_patterns = [
            (r'itr.*(\d+)', 'ITR - Year {}', 'Financial'),
            (r'balance\s*sheet.*(\d+)', 'Balance Sheet - Year {}', 'Financial'),
        ]
        for pattern, name_template, category in year_patterns:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                year = match.group(1)
                documents.append({
                    'name': name_template.format(year),
                    'description': f'{name_template.format(year)} as specified in tender',
                    'category': category,
                    'required': True,
                    'source': 'regex'
                })

        return documents

    def _extract_documents_llm(self, pdf_text: str) -> List[Dict]:
        """Extract document requirements using LLM analysis."""
        try:
            settings = db.load_settings()
            provider = settings.get('llm_provider', 'Disabled')
            if provider == 'Disabled':
                self._log('warn', 'LLM provider disabled, skipping LLM document extraction')
                return []

            if provider == 'Local LLM (LM Studio / Ollama)':
                self._local_llm_used = True

            # Keep input small — thinking models need tokens for reasoning + output.
            truncated_text = pdf_text[:4000] if len(pdf_text) > 4000 else pdf_text

            prompt = f"""Extract all document requirements from this tender document.
Capture explicit documents and evidence implied by eligibility clauses. For example, if the tender requires experience, turnover, or a tax registration, return the supporting proof as a required document.

Tender text:
{truncated_text}

Return a JSON array of documents with this exact format:
[
  {{
    "name": "Document Name",
    "description": "Brief description",
    "category": "Financial|Legal|Technical",
    "required": true
  }}
]

Return ONLY the JSON array, no other text."""

            response_text = llm.call_llm(
                prompt, provider,
                settings.get('llm_api_key', ''),
                settings.get('llm_base_url', ''),
                settings.get('llm_model', ''),
                response_json=True
            )

            # Strip thinking/reasoning block if present
            if '</think>' in response_text:
                response_text = response_text.split('</think>')[-1].strip()

            cleaned_json = llm.clean_json_response(response_text)

            # Try normal parse first; fall back to partial-repair for truncated output
            try:
                parsed_docs = json.loads(cleaned_json)
            except json.JSONDecodeError:
                repaired = llm.repair_truncated_json_array(cleaned_json)
                parsed_docs = json.loads(repaired)

            documents = []
            for doc in parsed_docs:
                if isinstance(doc, dict):
                    documents.append({
                        'name': doc.get('name', 'Unknown Document'),
                        'description': doc.get('description', ''),
                        'category': doc.get('category', 'Technical'),
                        'required': doc.get('required', True),
                        'source': 'llm'
                    })

            self._log('ok', f'LLM extracted {len(documents)} document requirements')
            return documents

        except Exception as e:
            self._log('err', f'LLM document extraction failed: {e}')
            return []

    # ------------------------------------------------------------------ #
    # GeM seller requirements                                             #
    # ------------------------------------------------------------------ #

    def _extract_gem_requirements(self, pdf_text: str) -> List[str]:
        """
        Extract required documents specified in the 'Document required from seller'
        section of GeM bids.
        """
        import re as _re
        if not pdf_text:
            return []

        # Try regex first
        pattern = r'Document\s*required\s*from\s*seller\s*\n\s*([\s\S]+?)(?=\n\s*(?:\*|Bid\s*Number|बड|सं>या|Dated|अितTर^|Additional|Consignee|\Z))'
        match = _re.search(pattern, pdf_text, _re.IGNORECASE)
        if match:
            raw_list = match.group(1).strip()
            normalized = " ".join(raw_list.split())
            docs = [d.strip() for d in normalized.split(",") if d.strip()]
            if docs:
                self._log('ok', f'Extracted {len(docs)} GeM requirements via regex: {docs}')
                return docs

        # Fallback to LLM if enabled
        settings = db.load_settings()
        provider = settings.get('llm_provider', 'Disabled')
        if provider not in ('', 'Disabled', None):
            try:
                self._log('info', 'Attempting LLM extraction of GeM portal requirements...')
                truncated_text = pdf_text[:12000] if len(pdf_text) > 12000 else pdf_text
                prompt = f"""Extract the list of required documents specified under the section 'Document required from seller' or 'विक्रेता से मांगे गए दस्तावेज़' in the following GeM tender text.
Return ONLY a comma-separated list of the document names (e.g. "Experience Criteria, Bidder Turnover, Certificate (Requested in ATC)").
If not found, return an empty string.

Text:
{truncated_text}"""
                response_text = llm.call_llm(
                    prompt, provider,
                    settings.get('llm_api_key', ''),
                    settings.get('llm_base_url', ''),
                    settings.get('llm_model', ''),
                    response_json=False
                )
                if response_text and response_text.strip():
                    docs = [d.strip() for d in response_text.split(",") if d.strip()]
                    docs = [d for d in docs if len(d) < 80 and not d.startswith("Here")]
                    if docs:
                        self._log('ok', f'Extracted {len(docs)} GeM requirements via LLM: {docs}')
                        return docs
            except Exception as e:
                self._log('warn', f'LLM GeM requirements extraction failed: {e}')

        return []
