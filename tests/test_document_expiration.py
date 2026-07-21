# -*- coding: utf-8 -*-
"""
test_document_expiration.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit tests for document expiration date parsing, status classification,
and document matching expiration metadata enrichment.
"""
import os
import sys
from datetime import date, timedelta
import pytest

# Ensure src paths are in sys.path
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, os.path.join(_ROOT, "src", "core"))
sys.path.insert(0, os.path.join(_ROOT, "src", "core", "workflow"))

import document_matcher
from document_matcher import DocumentMatcherMixin


class DummyMatcher(DocumentMatcherMixin):
    def __init__(self):
        self.matched_documents = {}
        self.missing_documents = []
        self.required_documents = []
        self.filing_folder = ""
        self.firm_name = "TestFirm"

    def _log(self, level, msg):
        pass


def test_check_document_expiration_explicit_dates():
    matcher = DummyMatcher()
    today = date.today()

    # Valid future date
    future_date = (today + timedelta(days=60)).strftime("%Y-%m-%d")
    res_valid = matcher._check_document_expiration("dummy_path/gst.pdf", future_date)
    assert res_valid['status'] == 'VALID'
    assert res_valid['is_expired'] is False
    assert res_valid['expiring_soon'] is False
    assert res_valid['days_remaining'] > 30

    # Expiring soon date (15 days)
    soon_date = (today + timedelta(days=15)).strftime("%Y-%m-%d")
    res_soon = matcher._check_document_expiration("dummy_path/gst.pdf", soon_date)
    assert res_soon['status'] == 'EXPIRING_SOON'
    assert res_soon['is_expired'] is False
    assert res_soon['expiring_soon'] is True
    assert res_soon['days_remaining'] == 15

    # Expired date (-10 days)
    past_date = (today - timedelta(days=10)).strftime("%Y-%m-%d")
    res_past = matcher._check_document_expiration("dummy_path/gst.pdf", past_date)
    assert res_past['status'] == 'EXPIRED'
    assert res_past['is_expired'] is True
    assert res_past['expiring_soon'] is False
    assert res_past['days_remaining'] == -10


def test_check_document_expiration_filename_regex():
    matcher = DummyMatcher()
    today = date.today()
    past_str = (today - timedelta(days=5)).strftime("%Y-%m-%d")
    
    filename = f"GST_Certificate_exp_{past_str}.pdf"
    res = matcher._check_document_expiration(filename)
    assert res['status'] == 'EXPIRED'
    assert res['is_expired'] is True
    assert res['expiry_date'] == past_str


def test_check_document_expiration_unknown():
    matcher = DummyMatcher()
    res = matcher._check_document_expiration("regular_document.pdf")
    assert res['status'] == 'UNKNOWN'
    assert res['is_expired'] is False
    assert res['days_remaining'] is None


def test_match_documents_with_expiries(tmp_path):
    matcher = DummyMatcher()
    
    # Create temporary dummy document file
    doc_file = tmp_path / "GST_Cert.pdf"
    doc_file.write_text("dummy pdf content")

    matcher.required_documents = [{"name": "gst"}]
    firm_docs = {"gst": str(doc_file)}
    
    today = date.today()
    past_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    firm_expiries = {"gst": past_date}

    matcher._match_documents(firm_documents=firm_docs, firm_expiries=firm_expiries)

    assert "gst" in matcher.matched_documents
    matched_entry = matcher.matched_documents["gst"]
    assert matched_entry['status'] == 'EXPIRED'
    assert matched_entry['is_expired'] is True
    assert matched_entry['expiry_date'] == past_date
