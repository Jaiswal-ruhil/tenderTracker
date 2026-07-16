"""
workflow/
~~~~~~~~~
Sub-modules for FilingWorkflow, split by responsibility.
Each module defines a Mixin class that FilingWorkflow inherits.
"""
from .pdf_handler import PdfHandlerMixin
from .text_extractor import TextExtractorMixin
from .document_matcher import DocumentMatcherMixin
from .folder_manager import FolderManagerMixin
from .report_generator import ReportGeneratorMixin
from .emd_extractor import EmdExtractorMixin

__all__ = [
    "PdfHandlerMixin",
    "TextExtractorMixin",
    "DocumentMatcherMixin",
    "FolderManagerMixin",
    "ReportGeneratorMixin",
    "EmdExtractorMixin",
]
