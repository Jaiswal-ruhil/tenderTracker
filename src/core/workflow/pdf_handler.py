"""
workflow/pdf_handler.py
~~~~~~~~~~~~~~~~~~~~~~~
Mixin: PDF download, bid-number verification, and embedded-link downloading.
"""
import os
import re
import urllib.parse
import urllib.request
import ssl
from typing import Dict, Optional

import db
import pdf_extractor
import scraper


class PdfHandlerMixin:
    """Methods for obtaining and validating the tender PDF."""

    # ------------------------------------------------------------------ #
    # Verification                                                         #
    # ------------------------------------------------------------------ #

    def _verify_pdf_bid_no(self, pdf_path: str, expected_bid_no: str) -> bool:
        """Verifies that the PDF file actually contains the expected bid number."""
        if not pdf_path or not os.path.exists(pdf_path):
            return False
        try:
            with open(pdf_path, 'rb') as f:
                text = pdf_extractor.extract_text(f.read())
            if not text:
                return False
            clean_text = " ".join(text.split()).lower()
            clean_bid = expected_bid_no.strip().lower()
            normalized_bid = clean_bid.replace("/", "").replace("_", "")
            normalized_text = clean_text.replace("/", "").replace("_", "")
            if clean_bid in clean_text or normalized_bid in normalized_text:
                return True
            return False
        except Exception:
            # Fallback to True to avoid false negatives on unreadable PDFs
            return True

    # ------------------------------------------------------------------ #
    # Download / ensure                                                    #
    # ------------------------------------------------------------------ #

    def _ensure_tender_pdf(self, tender_record: Dict) -> Optional[str]:
        """
        Ensure tender PDF is available locally; download if not present.

        Returns path to PDF file or None if failed.
        """
        bid_no = tender_record.get('bid_no', '')
        bid_url = tender_record.get('bid_url', '')
        existing_pdf = tender_record.get('pdf_path', '')

        # Check if PDF already exists locally
        if existing_pdf and os.path.exists(existing_pdf):
            if self._verify_pdf_bid_no(existing_pdf, bid_no):
                self._log('info', f'Using existing PDF: {existing_pdf}')
                return existing_pdf
            else:
                self._log('warn', f'Existing PDF {existing_pdf} does not match expected bid {bid_no}. Deleting and re-downloading.')
                try:
                    os.remove(existing_pdf)
                except Exception:
                    pass

        # Download PDF
        self._log('info', f'Downloading PDF for {bid_no}...')

        settings = db.load_settings()
        download_dir = settings.get('pdf_save_folder', '')
        if not download_dir:
            download_dir = os.path.join(os.path.expanduser('~'), 'Documents', 'TenderPDFs')

        os.makedirs(download_dir, exist_ok=True)

        try:
            if bid_url:
                # Bypass constructed fallback URL
                is_fallback_url = False
                id_m = re.search(r"([\dXx]+)$", bid_no)
                if id_m:
                    suffix = id_m.group(1)
                    if bid_url.rstrip("/").endswith(f"showbidDocument/{suffix}"):
                        is_fallback_url = True

                if is_fallback_url:
                    self._log('info', f'Bypassing constructed fallback URL for {bid_no}')
                else:
                    self._log('info', f'Attempting download using URL: {bid_url}')
                    pdf_path = scraper.download_tender_pdf(
                        bid_url, download_dir, log_fn=self._log, headless=True
                    )
                    if pdf_path:
                        if self._verify_pdf_bid_no(pdf_path, bid_no):
                            db.upsert_tender_field(bid_no, 'pdf_path', pdf_path)
                            return pdf_path
                        else:
                            self._log('warn', f'Downloaded PDF from URL does not match {bid_no}. Deleting and trying search fallback.')
                            try:
                                os.remove(pdf_path)
                            except Exception:
                                pass

            # Fallback to bid_no search
            if bid_no:
                self._log('info', f'Attempting search download for {bid_no}...')
                pdf_path = scraper.download_tender_pdf(
                    bid_no, download_dir, log_fn=self._log, headless=True
                )
                if pdf_path:
                    if self._verify_pdf_bid_no(pdf_path, bid_no):
                        db.upsert_tender_field(bid_no, 'pdf_path', pdf_path)
                        return pdf_path
                    else:
                        self._log('err', f'Downloaded PDF from search does not match {bid_no}. Deleting.')
                        try:
                            os.remove(pdf_path)
                        except Exception:
                            pass

        except Exception as e:
            self._log('err', f'PDF download failed: {e}')

        return None

    # ------------------------------------------------------------------ #
    # Embedded links                                                       #
    # ------------------------------------------------------------------ #

    def _download_embedded_links(self, pdf_path: str):
        """Find and download all embedded links (PDFs, Excel BOQs) from the tender PDF."""
        self._log('info', 'Scanning tender PDF for embedded links...')

        try:
            with open(pdf_path, 'rb') as f:
                pdf_bytes = f.read()
        except Exception as e:
            self._log('warn', f'Failed to read PDF for link extraction: {e}')
            return

        urls = set()

        # 1. Extract links via PyMuPDF (fitz) if available
        try:
            import fitz
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            for page in doc:
                for link in page.get_links():
                    uri = link.get("uri")
                    if uri and uri.strip().lower().startswith("http"):
                        urls.add(uri.strip())
            doc.close()
        except Exception:
            pass

        # 2. Extract links via pypdf (fallback if fitz is not installed)
        try:
            import pypdf
            import io
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            for page in reader.pages:
                if "/Annots" in page:
                    annots = page["/Annots"]
                    if not isinstance(annots, list):
                        annots = annots.get_object()
                    for annot in annots:
                        annot_obj = annot.get_object()
                        if annot_obj.get("/Subtype") == "/Link":
                            action = annot_obj.get("/A")
                            if action:
                                action_obj = action.get_object()
                                if "/URI" in action_obj:
                                    uri = action_obj["/URI"]
                                    if uri:
                                        urls.add(str(uri).strip())
        except Exception as e:
            self._log('warn', f'pypdf link annotation extraction failed: {e}')

        # 3. Extract plain text URLs using regex from extracted text
        try:
            text = pdf_extractor.extract_text(pdf_bytes)
            text_urls = re.findall(r'https?://[^\s)\]"\']+', text, re.IGNORECASE)
            for u in text_urls:
                if "gem.gov.in" in u.lower():
                    urls.add(u.strip())
        except Exception:
            pass

        if not urls:
            self._log('ok', 'No embedded links found in tender PDF.')
            return

        def get_valid_document_url_and_filename(url_str):
            valid_exts = ('.pdf', '.xls', '.xlsx', '.doc', '.docx', '.zip', '.csv')
            clean_u = url_str.rstrip('.')
            if "gem.gov.in" not in clean_u.lower():
                return None, None

            parsed_url = urllib.parse.urlparse(clean_u)

            # 1. Try to extract filename from URL path first
            path = parsed_url.path
            path_lower = path.lower()
            for ext in valid_exts:
                if path_lower.endswith(ext):
                    filename = os.path.basename(path)
                    return clean_u, filename

            # 2. Try to extract from query parameters
            qs = urllib.parse.parse_qs(parsed_url.query)
            for key, val_list in qs.items():
                for val in val_list:
                    val_lower = val.lower()
                    for ext in valid_exts:
                        if ext in val_lower:
                            possible_file = val.split('/')[-1].split('\\')[-1]
                            if possible_file.lower().endswith(ext):
                                return clean_u, possible_file

            # 3. Fallback: check if the whole URL contains any extension
            for ext in valid_exts:
                if ext in clean_u.lower():
                    return clean_u, None

            return None, None

        targets = []
        for url in urls:
            matched_url, filename = get_valid_document_url_and_filename(url)
            if matched_url:
                targets.append((matched_url, filename))

        if not targets:
            self._log('ok', 'No matching GeM document URLs found for download.')
            return

        self._log('info', f"Downloading {len(targets)} additional tender document(s)...")
        add_folder = os.path.join(self.filing_folder, "Additional_Tender_Documents")
        os.makedirs(add_folder, exist_ok=True)

        context = ssl._create_unverified_context()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        for idx, (url, filename) in enumerate(targets):
            try:
                if not filename:
                    ext = ".pdf"
                    for possible_ext in ('.pdf', '.xls', '.xlsx', '.doc', '.docx', '.zip', '.csv'):
                        if possible_ext in url.lower():
                            ext = possible_ext
                            break
                    filename = f"document_{idx+1}{ext}"

                safe_filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
                dest_path = os.path.join(add_folder, safe_filename)

                self._log('info', f"Downloading embedded document: {safe_filename}")
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=20, context=context) as response:
                    with open(dest_path, 'wb') as out_file:
                        out_file.write(response.read())

                self._log('ok', f"Successfully downloaded: {safe_filename}")
            except Exception as e:
                self._log('warn', f"Failed to download embedded link {url}: {e}")
