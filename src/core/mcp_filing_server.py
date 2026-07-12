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
            "This server cannot log in to GeM, upload files, sign, or submit a bid."
        ),
        port=port,
    )

    @mcp.tool()
    def prepare_filing(bid_no: str, firm_name: Optional[str] = None) -> Dict[str, Any]:
        """Create a reviewed-document pack and missing-document checklist for one confirmed tender."""
        tender = next((item for item in db.load_all_tenders() if item.get("bid_no") == bid_no), None)
        if not tender:
            return {"success": False, "error": f"Tender not found: {bid_no}"}
        return FilingWorkflow().start_filing_process(tender, firm_name=firm_name)

    return mcp


mcp = create_server()
