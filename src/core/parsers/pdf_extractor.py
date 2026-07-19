"""
pdf_extractor.py
~~~~~~~~~~~~~~~~
Fast PDF text and table extraction for the agentic tender parser.

Primary:  PyMuPDF (fitz)  — text blocks + layout
Tables:   pdfplumber      — structured table extraction
Fallback: pypdf           — when fitz is not installed
"""

import io
import re
import logger

# ---------------------------------------------------------------------------
# Optional imports — degrade gracefully if not installed
# ---------------------------------------------------------------------------
try:
    import fitz  # PyMuPDF
    _FITZ_OK = True
except ImportError:
    _FITZ_OK = False

try:
    import pdfplumber
    _PLUMBER_OK = True
except ImportError:
    _PLUMBER_OK = False

try:
    import pypdf
    _PYPDF_OK = True
except ImportError:
    _PYPDF_OK = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_text(pdf_bytes: bytes) -> str:
    """
    Extract full text from a PDF byte string.
    Uses fitz if available, falls back to pypdf.
    """
    if _FITZ_OK:
        return _fitz_extract_text(pdf_bytes)
    if _PYPDF_OK:
        return _pypdf_extract_text(pdf_bytes)
    raise RuntimeError("No PDF text extraction backend available. Install pymupdf or pypdf.")


def extract_tables(pdf_bytes: bytes) -> list:
    """
    Extract all tables from a PDF as a list of 2D lists.
    Each table is [[row0_col0, row0_col1, ...], [row1_col0, ...], ...]
    Returns [] if pdfplumber is not installed or no tables found.
    """
    if not _PLUMBER_OK:
        logger.log("warn", "pdfplumber not installed; table extraction unavailable.")
        return []
    try:
        tables = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                page_tables = page.extract_tables()
                if page_tables:
                    for tbl in page_tables:
                        # Clean None cells
                        clean = [
                            [cell if cell is not None else "" for cell in row]
                            for row in tbl
                        ]
                        tables.append(clean)
        return tables
    except Exception as e:
        logger.log("warn", f"pdfplumber table extraction failed: {e}")
        return []


def extract_text_and_tables(pdf_bytes: bytes) -> tuple:
    """
    Returns (full_text: str, tables: list[list[list[str]]]).
    Convenience wrapper combining extract_text() and extract_tables().
    """
    text = extract_text(pdf_bytes)
    tables = extract_tables(pdf_bytes)
    return text, tables


def extract_section(pdf_text: str, section_name: str, max_chars: int = 3000) -> str:
    """
    Find a named section in the full PDF text and return its content.
    Looks for the section header and returns up to max_chars characters
    until the next major section header or end of text.

    Examples of section_name: "Technical Specifications", "Terms and Conditions",
    "Annexure", "BOQ", "Eligibility", "EMD Detail"
    """
    if not pdf_text or not section_name:
        return ""

    # Build a flexible pattern that matches the section header
    escaped = re.escape(section_name.strip())
    pattern = re.compile(
        r"(?i)" + escaped.replace(r"\ ", r"[\s\-_]+"),
        re.IGNORECASE
    )
    match = pattern.search(pdf_text)
    if not match:
        # Try a looser search (first word only)
        first_word = section_name.split()[0]
        match = re.search(re.escape(first_word), pdf_text, re.IGNORECASE)
        if not match:
            return ""

    start = match.start()
    snippet = pdf_text[start: start + max_chars]

    # Stop at the next major section header (ALL CAPS line or "Section X")
    next_header = re.search(
        r"\n\s*(?:[A-Z][A-Z\s]{8,}|Section\s+\d+|Annexure\s+[A-Z0-9])",
        snippet[len(match.group()):]  # skip the matched header itself
    )
    if next_header:
        snippet = snippet[: len(match.group()) + next_header.start()]


    return snippet.strip()


def is_scanned_pdf(pdf_text: str, min_char_density: int = 100) -> bool:
    """
    Heuristic: if the extracted text has fewer than min_char_density
    printable characters, the PDF is likely a scanned image requiring OCR.
    """
    if not pdf_text:
        return True
    printable = sum(1 for c in pdf_text if c.isprintable() and not c.isspace())
    return printable < min_char_density


def tables_to_text(tables: list) -> str:
    """
    Convert extracted tables to a readable plain-text representation
    suitable for inclusion in an LLM prompt.
    """
    if not tables:
        return ""
    parts = []
    for i, table in enumerate(tables, 1):
        parts.append(f"[Table {i}]")
        for row in table:
            parts.append(" | ".join(str(c).strip() for c in row))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fitz_extract_text(pdf_bytes: bytes) -> str:
    """Extract text using PyMuPDF — preserves layout better than pypdf."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = []
        for page in doc:
            pages.append(page.get_text("text"))
        doc.close()
        return "\n".join(pages)
    except Exception as e:
        logger.log("warn", f"fitz extraction failed: {e}. Falling back to pypdf.")
        if _PYPDF_OK:
            return _pypdf_extract_text(pdf_bytes)
        return ""


def _pypdf_extract_text(pdf_bytes: bytes) -> str:
    """Extract text using pypdf as a fallback."""
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        pages = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                pages.append(t)
        return "\n".join(pages)
    except Exception as e:
        logger.log("warn", f"pypdf extraction failed: {e}")
        return ""
