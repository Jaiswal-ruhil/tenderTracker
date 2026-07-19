"""Analysis MCP: deterministic and LLM-assisted tender assessment."""

import asyncio
import os
from typing import Any, Dict, List

from mcp.server.fastmcp import FastMCP

import db
import llm
import parser
import pdf_extractor
from llm_client import LMStudioClient


def _run_async(coro):
    return asyncio.run(coro)


def create_server(port: int = 8102) -> FastMCP:
    mcp = FastMCP(
        "TenderTracker Analysis",
        instructions="Use this server to parse and assess tender data. It does not modify tender status.",
        port=port,
    )

    @mcp.tool()
    def extract_bid_blocks(text: str) -> List[Dict[str, Any]]:
        """Deterministically parse copied GeM text into tender records."""
        records = []
        for block in parser.split_blocks(text):
            record = parser.parse_one(block)
            if record and record.get("bid_no"):
                records.append(record)
        return records

    @mcp.tool()
    def classify_bid(bid_obj: Dict[str, Any]) -> Dict[str, Any]:
        """Classify a tender with the configured local LM Studio model."""
        client = LMStudioClient()
        try:
            return _run_async(client.classify_bid_async(bid_obj)).model_dump()
        except Exception as exc:
            return {"error": f"Classification failed: {exc}"}
        finally:
            _run_async(client.close())

    @mcp.tool()
    def generate_quote_requirements(bid_obj: Dict[str, Any]) -> Dict[str, Any]:
        """Create a preliminary EMD, ePBG, turnover, experience, and MII checklist."""
        checklist = []
        if bid_obj.get("emd", "No") not in ("No", "NA"):
            checklist.append(f"Prepare EMD: {bid_obj['emd']}")
        else:
            checklist.append("Verify MSE/Startup evidence for EMD exemption.")
        if bid_obj.get("epbg", "No") not in ("No", "NA"):
            checklist.append(f"Prepare ePBG: {bid_obj['epbg']}")
        if bid_obj.get("min_turnover") not in (None, "", "N/A", "NA"):
            checklist.append(f"Verify turnover evidence: {bid_obj['min_turnover']}")
        if bid_obj.get("exp_years") not in (None, "", "N/A", "NA"):
            checklist.append(f"Verify experience evidence: {bid_obj['exp_years']} years")
        if bid_obj.get("mii") == "Yes":
            checklist.append("Prepare Make in India declaration.")
        checklist.append(f"Verify delivery feasibility: {bid_obj.get('location', 'N/A')}")
        return {"bid_no": bid_obj.get("bid_no"), "checklist": checklist}

    @mcp.tool()
    def match_company_products(bid_obj: Dict[str, Any]) -> Dict[str, Any]:
        """
        Match tender item text against the local company product catalogue.
        Uses AI-enhanced similarity scoring for better matching accuracy.
        """
        item_text = bid_obj.get("items", "").lower()
        category = bid_obj.get("category", "").lower()
        matches = []
        
        # Load products and perform AI-enhanced matching
        products = db.load_all_products()
        for product in products:
            name = product.get("name", "").lower()
            description = product.get("description", "").lower()
            
            # Basic keyword matching
            if name and (name in item_text or name in category or description in item_text):
                matches.append({
                    "product": product,
                    "match_type": "keyword",
                    "confidence": 0.8
                })
            else:
                # AI-enhanced similarity scoring
                from filing_workflow import FilingWorkflow
                workflow = FilingWorkflow()
                similarity = workflow._calculate_similarity_score(name, item_text)
                if similarity > 0.6:
                    matches.append({
                        "product": product,
                        "match_type": "ai_similarity",
                        "confidence": similarity
                    })
        
        # Sort by confidence
        matches.sort(key=lambda x: x["confidence"], reverse=True)
        
        return {
            "bid_no": bid_obj.get("bid_no"),
            "match_score": max([m["confidence"] for m in matches], default=0.0),
            "matching_products": [m["product"] for m in matches],
            "match_details": matches,
            "missing_products": [] if matches else [category or "General items"],
        }

    @mcp.tool()
    def parse_tender_pdf(pdf_path: str) -> Dict[str, Any]:
        """Parse a local tender PDF and save the resulting record to the local database."""
        if not os.path.isfile(pdf_path):
            return {"error": f"PDF file not found: {pdf_path}"}
        try:
            with open(pdf_path, "rb") as source:
                text = pdf_extractor.extract_text(source.read())
            settings = db.load_settings()
            record = llm.llm_parse_tender_agentic(
                parser.convert_pdf_text_to_markdown(text),
                settings.get("llm_provider", "Disabled"),
                settings.get("llm_api_key", ""),
                settings.get("llm_base_url", "http://localhost:1234"),
                settings.get("llm_model", ""),
            )
            if record:
                record.update({"pdf_path": os.path.abspath(pdf_path), "is_fetched": True})
                db.upsert_tender(record)
            return record or {"error": "No tender record could be extracted"}
        except Exception as exc:
            return {"error": str(exc)}

    return mcp


mcp = create_server()
