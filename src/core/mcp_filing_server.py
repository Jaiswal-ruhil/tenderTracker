"""Filing MCP: document-pack preparation only; it never submits a bid."""

from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

import db
from filing_workflow import FilingWorkflow


def create_server(port: int = 8103) -> FastMCP:
    mcp = FastMCP(
        "TenderTracker Filing",
        instructions=(
            "Prepare a filing folder only after the user has confirmed the target bid. "
            "This server cannot log in to GeM, upload files, sign, or submit a bid. "
            "It includes AI-enhanced document matching, GEM compliance validation, "
            "and automated document validation with detailed reporting."
        ),
        port=port,
    )

    @mcp.tool()
    def prepare_filing(bid_no: str, firm_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a reviewed-document pack and missing-document checklist for one confirmed tender.
        
        Returns enhanced results including:
        - validation_results: GEM compliance validation for all documents
        - gem_requirements_mapping: Document mappings for GEM portal upload fields
        - processing_stats: Statistics about the filing process
        - matched_documents: AI-enhanced document matches with confidence scores
        - missing_documents: List of required documents that couldn't be matched
        """
        tender = next((item for item in db.load_all_tenders() if item.get("bid_no") == bid_no), None)
        if not tender:
            return {"success": False, "error": f"Tender not found: {bid_no}"}
        
        workflow = FilingWorkflow()
        result = workflow.start_filing_process(tender, firm_name=firm_name)
        
        # Return extended results with validation and mapping data
        return {
            "success": result.get("success", False),
            "bid_no": bid_no,
            "filing_folder": result.get("filing_folder"),
            "matched_documents": result.get("matched_documents", {}),
            "missing_documents": result.get("missing_documents", []),
            "validation_results": workflow.validation_results,
            "processing_stats": workflow.processing_stats,
            "checklist_path": result.get("checklist_path"),
            "summary_path": result.get("summary_path"),
            "validation_report_path": result.get("validation_report_path"),
            "gem_mapping_path": result.get("gem_mapping_path"),
            "error": result.get("error")
        }

    @mcp.tool()
    def validate_document_integrity(doc_path: str) -> Dict[str, Any]:
        """
        Validate a single document for GEM compliance.
        Checks file size (10MB limit), PDF page count (100 pages limit), and file integrity.
        """
        workflow = FilingWorkflow()
        validation = workflow._validate_document_integrity(doc_path)
        return validation

    @mcp.tool()
    def get_gem_requirements_mapping(bid_no: str) -> Dict[str, Any]:
        """
        Get the GEM portal document requirements mapping for a tender.
        Returns the mapping of required documents to upload fields.
        """
        tender = next((item for item in db.load_all_tenders() if item.get("bid_no") == bid_no), None)
        if not tender:
            return {"success": False, "error": f"Tender not found: {bid_no}"}
        
        workflow = FilingWorkflow()
        # Initialize workflow to access category and firm info
        workflow._initialize_firm_and_category(tender)
        
        # Get GEM requirements for the category
        return {
            "bid_no": bid_no,
            "category": workflow.category,
            "gem_requirements": workflow._get_gem_requirements()
        }

    return mcp


mcp = create_server()
