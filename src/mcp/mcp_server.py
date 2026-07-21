# Model Context Protocol (MCP) Server for TenderTracker
# Exposes Python parsers, SQLite queries, and async LLM client reasoning tools for LLMs.

import os
import sys
import json
import asyncio
from typing import List, Dict, Any, Optional

# Add src and src/core to sys.path so imports work from any execution context
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'core'))

from mcp.server.fastmcp import FastMCP
import db
import parser
import vector_search
from llm_client import LMStudioClient

# Initialize FastMCP server
mcp = FastMCP("TenderTracker")

# Helper to run async functions synchronously for FastMCP tools
def run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        return asyncio.run_coroutine_threadsafe(coro, loop).result()
    else:
        return asyncio.run(coro)

@mcp.tool()
def extract_bid_blocks(text: str) -> List[Dict[str, Any]]:
    """
    Parse a copied text block or HTML from the GeM portal and return a list of parsed BidObjects.
    This layer is strictly deterministic and uses no LLM calls.
    """
    blocks = parser.split_blocks(text)
    results = []
    for blk in blocks:
        parsed_record = parser.parse_one(blk)
        if parsed_record and parsed_record.get("bid_no"):
            results.append(parsed_record)
    return results

@mcp.tool()
def get_bid(bid_no: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a single BidObject from the database by its unique Bid Number using indexed O(1) lookup.
    """
    tender = db.get_tender(bid_no)
    if tender and "embedding" in tender:
        tender = dict(tender)
        tender.pop("embedding", None)
    return tender

@mcp.tool()
def classify_bid(bid_obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform semantic reasoning and classification on a BidObject using local LM Studio inference.
    Saves and returns structured JSON conforming to the Classification Schema.
    """
    client = LMStudioClient()
    try:
        result = run_async(client.classify_bid_async(bid_obj))
        return result.model_dump()
    except Exception as e:
        return {"error": f"Failed to classify bid: {str(e)}"}
    finally:
        run_async(client.close())

@mcp.tool()
def search_bids(
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    department: Optional[str] = None,
    end_date: Optional[str] = None,
    product: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Search and filter stored tenders/bids using indexed text search and keyword/category filters.
    """
    if keyword:
        tenders = db.text_search_tenders(keyword, limit=50)
    else:
        tenders = db.load_all_tenders()

    filtered = []
    for t in tenders:
        if category and category.lower() not in t.get("category", "").lower():
            continue
        if department and department.lower() not in t.get("dept", "").lower():
            continue
        if end_date and t.get("end_date") != end_date:
            continue
        if product and product.lower() not in t.get("items", "").lower():
            continue
        
        t_copy = dict(t)
        t_copy.pop("embedding", None)
        filtered.append(t_copy)
    return filtered

@mcp.tool()
def semantic_search_bids(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Perform fast sub-10ms semantic vector search on tenders using the FAISS/Annoy index.
    Returns the most relevant tender records matched by context and meaning.
    """
    try:
        matched_bid_nos = vector_search.search_vector_index(query, top_k=top_k)
        results = []
        for bid_no in matched_bid_nos:
            tender = db.get_tender(bid_no)
            if tender:
                t_copy = dict(tender)
                t_copy.pop("embedding", None)
                results.append(t_copy)
        return results
    except Exception as exc:
        return [{"error": f"Semantic search failed: {exc}"}]

@mcp.tool()
def generate_quote_requirements(bid_obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a quotation requirements checklist for a bid based on its parameters (EMD, ePBG, Experience).
    """
    bid_no = bid_obj.get("bid_no", "N/A")
    checklist = []
    
    # Check EMD Advisory bank and requirements
    emd_val = bid_obj.get("emd", "No")
    if emd_val != "No" and emd_val != "NA":
        checklist.append(f"Prepare and deposit Earnest Money Deposit (EMD) of value: {emd_val}")
    else:
        checklist.append("EMD is Exempted/Not Required. Verify if MSE/Startup certificates are ready.")

    # Check ePBG advisory
    epbg_val = bid_obj.get("epbg", "No")
    if epbg_val != "No" and epbg_val != "NA":
        checklist.append(f"Prepare for Performance Bank Guarantee (ePBG) of value: {epbg_val}")

    # Check Turnover Criteria
    turnover = bid_obj.get("min_turnover", "N/A")
    if turnover != "N/A" and turnover != "NA":
        checklist.append(f"Retrieve Audited Balance Sheet & CA Certificate confirming average annual turnover of {turnover}")

    # Past Experience
    exp = bid_obj.get("exp_years", "N/A")
    if exp != "N/A" and exp != "NA":
        checklist.append(f"Retrieve past Performance Certificates & Invoices proving {exp} years of past experience in similar work")

    # MII (Make In India) Compliance
    mii = bid_obj.get("mii", "No")
    if mii == "Yes":
        checklist.append("Locational local content declaration required (MII Compliance Certificate)")

    # Delivery address
    loc = bid_obj.get("location", "N/A")
    checklist.append(f"Verify logistical route and delivery capabilities to: {loc}")

    return {
        "bid_no": bid_no,
        "checklist": checklist
    }

@mcp.tool()
def match_company_products(bid_obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Match the bid items against our stored company products database.
    Returns match score, list of matching products, and missing product categories.
    """
    items_desc = bid_obj.get("items", "").lower()
    category = bid_obj.get("category", "").lower()
    
    products = db.load_all_products()
    matching = []
    missing = []
    
    # Basic keyword mapping/matching
    for p in products:
        p_name = p.get("name", "").lower()
        p_desc = p.get("description", "").lower()
        if p_name in items_desc or p_name in category or p_desc in items_desc:
            matching.append(p)
            
    # Calculate score
    score = 0.0
    if matching:
        score = min(1.0, len(matching) / max(1.0, len(products) * 0.5))
    else:
        # Check if category contains any common keywords
        missing.append(category or "General items")
        
    return {
        "bid_no": bid_obj.get("bid_no"),
        "match_score": score,
        "matching_products": matching,
        "missing_products": missing
    }

@mcp.tool()
def add_tender_to_db(record: dict) -> dict:
    """
    Upsert (insert or update) a single tender record in the SQLite database.
    """
    if "bid_no" not in record or not record.get("bid_no"):
        return {"error": "Missing required field 'bid_no'"}
    
    try:
        db.upsert_tender(record)
        return {"success": True, "bid_no": record["bid_no"]}
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
def update_tender_field(bid_no: str, field: str, value: str) -> dict:
    """
    Surgically update a single field of an existing tender/bid in the database.
    """
    try:
        success = db.upsert_tender_field(bid_no, field, value)
        return {"success": success, "bid_no": bid_no, "field": field, "value": value}
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
def rebuild_search_index() -> dict:
    """
    Rebuild the FAISS / Annoy vector search index using the embeddings cached in the database.
    """
    try:
        success = vector_search.rebuild_vector_index()
        return {"success": success}
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
def parse_tender_pdf_agentic(pdf_path: str) -> dict:
    """
    Run the full agentic tool-calling loop on a local PDF file.
    Uses PyMuPDF (fitz) text extraction + LLM tool-calling loop to produce the TenderRecord.
    """
    if not os.path.exists(pdf_path):
        return {"error": f"PDF file not found at: {pdf_path}"}
    try:
        import pdf_extractor
        import llm
        import db

        # Extract
        pdf_bytes = open(pdf_path, "rb").read()
        text = pdf_extractor.extract_text(pdf_bytes)
        md_text = parser.convert_pdf_text_to_markdown(text)

        # Get settings
        settings = db.load_settings()
        provider = settings.get("llm_provider", "Local LLM (LM Studio / Ollama)")
        api_key = settings.get("llm_api_key", "")
        base_url = settings.get("llm_base_url", "http://localhost:1234")
        model = settings.get("llm_model", "")

        # Run agent
        record = llm.llm_parse_tender_agentic(md_text, provider, api_key, base_url, model)
        if record:
            record["pdf_path"] = os.path.abspath(pdf_path)
            record["is_fetched"] = True
            db.upsert_tender(record)
        return record
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":

    mcp.run()
