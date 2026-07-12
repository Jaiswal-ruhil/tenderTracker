import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'core')))

import filing_workflow


class TestFilingWorkflow(unittest.TestCase):
    def test_extracts_upload_proofs_from_combined_eligibility_clause(self):
        text = (
            '03 Years Experience of Sugar Mills and Last Three year Turn over, '
            'Aadhar card, Pan Card, GST Certificate will be necessary. '
            'The proof will be uploaded by Tenderer.'
        )

        workflow = filing_workflow.FilingWorkflow(log_fn=lambda *_: None)
        documents = workflow._extract_documents_regex(text)
        documents_by_name = {document['name']: document for document in documents}

        self.assertEqual(set(documents_by_name), {
            'Experience Proof - 3 Years',
            'Turnover Proof - Last 3 Years',
            'Aadhaar Card',
            'PAN Card',
            'GST Certificate',
        })
        self.assertEqual(
            documents_by_name['Experience Proof - 3 Years']['description'],
            'Proof of 3 years of experience of sugar mills as specified in tender document',
        )
        self.assertEqual(documents_by_name['Aadhaar Card']['category'], 'Legal')

    def test_extracts_eligibility_evidence_when_word_order_and_format_change(self):
        cases = [
            (
                'Past experience: 3 years in supply of electrical goods. '
                'Turnover for previous 3 financial years must be submitted.',
                {'Experience Proof - 3 Years', 'Turnover Proof - Last 3 Years'},
            ),
            (
                'Experience of five yrs in sugar industry is mandatory. '
                'Bidder shall upload turnover for the last five years.',
                {'Experience Proof - 5 Years', 'Turnover Proof - Last 5 Years'},
            ),
            (
                'Minimum 2 years of similar experience is required; '
                'last two-year turn over proof is required.',
                {'Experience Proof - 2 Years', 'Turnover Proof - Last 2 Years'},
            ),
        ]

        workflow = filing_workflow.FilingWorkflow(log_fn=lambda *_: None)
        for text, expected_names in cases:
            with self.subTest(text=text):
                names = {document['name'] for document in workflow._extract_documents_regex(text)}
                self.assertTrue(expected_names.issubset(names))

    def test_matches_documents_and_creates_self_contained_filing_folder(self):
        settings = {'firms': [{
            'name': 'Preferred Firm',
            'documents': {'gst': 'gst.pdf', 'pan': 'pan.pdf'},
        }]}
        tender = {
            'bid_no': 'GEM/2026/B/42',
            'pdf_path': 'source.pdf',
            'matched_firm': 'Preferred Firm',
            'items': 'Test item',
        }
        text = 'GST certificate and PAN card are required for submission.'

        workflow = filing_workflow.FilingWorkflow(log_fn=lambda *_: None)
        with patch.object(filing_workflow.db, 'load_settings', return_value=settings), \
             patch.object(filing_workflow.os.path, 'exists', return_value=True), \
             patch.object(workflow, '_extract_pdf_text', return_value=text), \
             patch.object(workflow, '_extract_text_from_additional_files', return_value={}), \
             patch.object(workflow, '_create_filing_folder', return_value='filing-folder'), \
             patch.object(workflow, '_copy_tender_pdf') as copy_tender_pdf, \
             patch.object(workflow, '_copy_documents_to_folder') as copy_documents, \
             patch.object(workflow, '_generate_checklist', return_value='checklist.txt'), \
             patch.object(workflow, '_generate_summary', return_value='summary.txt'):
            result = workflow.start_filing_process(tender)

        self.assertTrue(result['success'])
        self.assertEqual(result['required_count'], 2)
        self.assertEqual(result['matched_count'], 2)
        self.assertEqual(result['missing_count'], 0)
        copy_tender_pdf.assert_called_once_with('source.pdf')
        copy_documents.assert_called_once()
        self.assertEqual(result['checklist_file'], 'checklist.txt')
        self.assertEqual(result['summary_file'], 'summary.txt')

    def test_reused_workflow_does_not_keep_prior_state(self):
        workflow = filing_workflow.FilingWorkflow(log_fn=lambda *_: None)
        workflow.required_documents = [{'name': 'Old'}]
        workflow.matched_documents = {'Old': {}}
        workflow.missing_documents = [{'name': 'Old'}]
        workflow.filing_folder = 'old-folder'

        result = workflow.start_filing_process({})

        self.assertFalse(result['success'])
        self.assertEqual(workflow.required_documents, [])
        self.assertEqual(workflow.matched_documents, {})
        self.assertEqual(workflow.missing_documents, [])
        self.assertEqual(workflow.filing_folder, '')
