# -*- coding: utf-8 -*-
"""
test_filing_step_timings.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit tests for per-step execution timing tracking and individual step log exporting.
"""
import os
import sys
import json
import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, os.path.join(_ROOT, "src", "core"))
sys.path.insert(0, os.path.join(_ROOT, "src", "core", "workflow"))

import filing_workflow
from filing_workflow import FilingWorkflow


def test_save_step_logs_and_timings(tmp_path):
    workflow = FilingWorkflow()
    workflow.filing_folder = str(tmp_path)
    workflow.processing_stats = {"step_1_sec": 1.25, "step_2_sec": 0.45}

    step_logs = {
        "step_1_extraction": ["Extracted 4 required documents", "Mapped GEM criteria"],
        "step_2_document_matching": ["Matched GST (valid)", "Matched MSME (valid)"]
    }

    out_dir = workflow._save_step_logs_and_timings(step_logs=step_logs)
    assert os.path.exists(out_dir)

    # Check step_timings.json
    timings_file = os.path.join(out_dir, "step_timings.json")
    assert os.path.exists(timings_file)
    with open(timings_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        assert data["step_1_sec"] == 1.25

    # Check individual step log files
    log_1 = os.path.join(out_dir, "step_1_extraction.log")
    log_2 = os.path.join(out_dir, "step_2_document_matching.log")
    assert os.path.exists(log_1)
    assert os.path.exists(log_2)

    with open(log_1, 'r', encoding='utf-8') as f:
        content_1 = f.read()
        assert "Extracted 4 required documents" in content_1

    with open(log_2, 'r', encoding='utf-8') as f:
        content_2 = f.read()
        assert "Matched GST (valid)" in content_2
