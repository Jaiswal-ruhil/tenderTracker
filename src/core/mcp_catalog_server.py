"""Catalog MCP: tender search and approved database mutations."""

import json
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

import db
import vector_search


def create_server(port: int = 8101) -> FastMCP:
    mcp = FastMCP(
        "TenderTracker Catalog",
        instructions=(
            "Use this server to retrieve, search, and maintain TenderTracker "
            "records. Update only fields explicitly requested by the user."
        ),
        port=port,
    )

    @mcp.tool()
    def get_bid(bid_no: str) -> Optional[Dict[str, Any]]:
        """Retrieve one tender by its GeM bid number."""
        return next((t for t in db.load_all_tenders() if t.get("bid_no") == bid_no), None)

    @mcp.tool()
    def search_bids(
        keyword: Optional[str] = None,
        category: Optional[str] = None,
        department: Optional[str] = None,
        end_date: Optional[str] = None,
        product: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search stored tenders by keyword, category, department, deadline, or item."""
        results = []
        for tender in db.load_all_tenders():
            if keyword and keyword.lower() not in json.dumps(tender).lower():
                continue
            if category and category.lower() not in tender.get("category", "").lower():
                continue
            if department and department.lower() not in tender.get("dept", "").lower():
                continue
            if end_date and tender.get("end_date") != end_date:
                continue
            if product and product.lower() not in tender.get("items", "").lower():
                continue
            results.append(tender)
        return results

    @mcp.tool()
    def add_tender(record: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update a tender record. A non-empty bid_no is required."""
        if not record.get("bid_no"):
            return {"success": False, "error": "Missing required field 'bid_no'"}
        try:
            db.upsert_tender(record)
            return {"success": True, "bid_no": record["bid_no"]}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @mcp.tool()
    def update_tender_field(bid_no: str, field: str, value: str) -> Dict[str, Any]:
        """Update one user-approved field on an existing tender."""
        try:
            return {
                "success": db.upsert_tender_field(bid_no, field, value),
                "bid_no": bid_no,
                "field": field,
                "value": value,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @mcp.tool()
    def rebuild_search_index() -> Dict[str, Any]:
        """Rebuild the local tender semantic-search index."""
        try:
            return {"success": vector_search.rebuild_vector_index()}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    return mcp


mcp = create_server()
