"""
tender_tools.py
~~~~~~~~~~~~~~~
Python extraction tool functions exposed to the LLM as tool-calling schemas.

Each function:
  - Accepts a `pdf_text` string (and optional kwargs)
  - Returns a plain dict or string — no LLM calls inside
  - Is registered in TOOL_REGISTRY and exposed as a JSON schema

The LLM (running in LM Studio) decides which tools to call.
The agentic loop in llm_agent.py executes them and feeds the
results back to the LLM until a final TenderRecord is produced.
"""

import re
import json
import logger

# ---------------------------------------------------------------------------
# Individual tool functions
# ---------------------------------------------------------------------------

def extract_bid_metadata(pdf_text: str) -> dict:
    """
    Extract core bid identification fields:
    bid_no, bid_url, start_date, end_date, bid_opening, est_value.
    """
    r = {}

    # Bid number — standard GeM format
    m = re.search(r"(GEM/\d{4}/[A-Z0-9]+/[\dXx]+)", pdf_text, re.I)
    if m:
        r["bid_no"] = m.group(1).strip().upper()
        # Construct URL from trailing digits
        id_m = re.search(r"([\dXx]+)$", r["bid_no"])
        if id_m:
            r["bid_url"] = f"https://bidplus.gem.gov.in/showbidDocument/{id_m.group(1)}"

    # Dates
    m = re.search(r"Bid\s*End\s*Date\s*(?:/\s*Time)?\s*[:\n]\s*([0-9]{2}[-/][0-9]{2}[-/][0-9]{4}[^\n]*)", pdf_text, re.I)
    if m: r["end_date"] = m.group(1).strip()

    m = re.search(r"(?:Dated|Bid\s*Start\s*Date)\s*[:\n]\s*([0-9]{2}[-/][0-9]{2}[-/][0-9]{4})", pdf_text, re.I)
    if m: r["start_date"] = m.group(1).strip()

    m = re.search(r"Bid\s*Opening\s*(?:Date/Time|Date)?\s*[:\n\s]*([0-9]{2}[-/][0-9]{2}[-/][0-9]{4}[^\n]*)", pdf_text, re.I)
    if m: r["bid_opening"] = m.group(1).strip()

    # Estimated value
    m = re.search(r"Estimated\s*Bid\s*Value(?:[^\n]*\n){0,3}?[^\n]*?(\d[\d,\.]+)", pdf_text, re.I)
    if m: r["est_value"] = m.group(1).replace(",", "").strip()

    return r


def extract_department_info(pdf_text: str) -> dict:
    """
    Extract ministry, department, organisation, and office names.
    """
    r = {}
    m = re.search(r"Ministry[/\w\s]*?Name\s*[:\n]\s*(.+)", pdf_text, re.I)
    if m: r["ministry"] = m.group(1).strip()

    m = re.search(r"Department\s*Name\s*[:\n]\s*([\s\S]*?)(?=\n(?:Organisation|Office|Bid|संगठन|\Z))", pdf_text, re.I)
    if m:
        dept_lines = [ln.strip() for ln in m.group(1).splitlines() if ln.strip()]
        if dept_lines: r["dept"] = dept_lines[0]
    if not r.get("dept"):
        m = re.search(r"Department\s*Name\s*[:\n]\s*(.+)", pdf_text, re.I)
        if m: r["dept"] = m.group(1).strip()

    m = re.search(r"Organisation\s*Name\s*[:\n]\s*(.+)", pdf_text, re.I)
    if m: r["organisation"] = m.group(1).strip()

    m = re.search(r"Office\s*Name\s*[:\n]\s*(.+)", pdf_text, re.I)
    if m: r["office"] = m.group(1).strip()

    return r


def extract_eligibility_criteria(pdf_text: str) -> dict:
    """
    Extract eligibility fields: min_turnover, exp_years, MII, MSE preferences,
    startup relaxation.
    """
    r = {}

    m = re.search(r"Minimum\s*Average\s*Annual\s*Turnover(?:[^\n]*\n){0,3}?[^\n]*?(\d[\d\.]*\s*(?:Lakhs?|Crores?|L|Cr)?)", pdf_text, re.I)
    if m: r["min_turnover"] = m.group(1).strip()

    m = re.search(r"Years\s*of\s*Past\s*Experience(?:[^\n]*\n){0,3}?[^\n]*?(\d[\d\.]*\s*(?:Years?|Yrs?)?)", pdf_text, re.I)
    if m: r["exp_years"] = m.group(1).strip()

    for field, pattern in [
        ("mii",         r"MII\s*Compliance(?:[^\n]*\n){0,3}?[^\n]*?(Yes|No)"),
        ("mse_pref",    r"MSE\s*Purchase\s*Preference(?:[^\n]*\n){0,3}?[^\n]*?(Yes|No)"),
        ("mse_relax",   r"MSE\s*Relaxation(?:[^\n]*\n){0,3}?[^\n]*?(Yes|No)"),
        ("startup_relax", r"Startup\s*Relaxation(?:[^\n]*\n){0,3}?[^\n]*?(Yes|No)"),
    ]:
        m = re.search(pattern, pdf_text, re.I)
        if m: r[field] = m.group(1).strip()

    return r



def extract_financial_security(pdf_text: str) -> dict:
    """
    Extract EMD and ePBG details (required yes/no and amounts if present).
    """
    r = {}
    lower = pdf_text.lower()

    # Isolate EMD and ePBG blocks to prevent cross-talk
    emd_idx = lower.find("emd detail")
    epbg_idx = lower.find("epbg detail")

    emd_block = ""
    if emd_idx != -1:
        end = epbg_idx if (epbg_idx != -1 and epbg_idx > emd_idx) else emd_idx + 1500
        emd_block = pdf_text[emd_idx:end]

    epbg_block = ""
    if epbg_idx != -1:
        epbg_block = pdf_text[epbg_idx: epbg_idx + 1500]

    # EMD
    if emd_block:
        if re.search(r"advisory\s*bank|emd\s*amount|\bamount\b", emd_block, re.I):
            r["emd"] = "Yes"
            amt = re.search(r"(?:EMD\s*Amount|Amount)\s*[:\n]\s*([\d,\.]+)", emd_block, re.I)
            if amt: r["emd_amount"] = amt.group(1).replace(",", "").strip()
        elif re.search(r"Required\s*[:\n]\s*Yes", emd_block, re.I):
            r["emd"] = "Yes"
        else:
            r["emd"] = "No"
    else:
        r["emd"] = "No"

    # ePBG
    if epbg_block:
        m = re.search(r"Required\s*[:\n]\s*(Yes|No)", epbg_block, re.I)
        if m:
            r["epbg"] = m.group(1).strip()
        elif re.search(r"advisory\s*bank|duration", epbg_block, re.I):
            r["epbg"] = "Yes"
        else:
            r["epbg"] = "No"
    else:
        r["epbg"] = "No"

    return r


def extract_item_details(pdf_text: str) -> dict:
    """
    Extract item/category, quantity, contract duration, evaluation method,
    bid type, and Bid-to-RA flag.
    """
    r = {}

    # Item category (multi-line aware)
    pos = re.search(r"Item\s*Category\s*[:\n]\s*", pdf_text, re.I)
    if pos:
        sub = pdf_text[pos.end(): pos.end() + 500]
        stop_kws = ["ministry", "department", "organisation", "office", "dated",
                    "bid end", "estimated", "evaluation", "consignee"]
        lines = []
        for ln in sub.splitlines():
            cleaned = ln.strip()
            if not cleaned: continue
            if any(kw in cleaned.lower() for kw in stop_kws): break
            if re.match(r"^[A-Za-z0-9/\s]+:", cleaned): break
            lines.append(cleaned)
        item_cat = " ".join(lines).strip()
        if item_cat:
            if "-" in item_cat:
                parts = re.split(r"\s*-\s*", item_cat, maxsplit=1)
                r["category"] = parts[0].strip()
                r["items"] = parts[1].strip()
            else:
                r["category"] = item_cat
                r["items"] = item_cat

    # Quantity
    m = re.search(r"Total\s*Quantity\s*[:\n]\s*(\d+)", pdf_text, re.I)
    if not m:
        m = re.search(r"Quantity\s*[:\n]\s*(\d+)", pdf_text, re.I)
    if m: r["quantity"] = m.group(1).strip()

    # Contract duration
    m = re.search(r"Contract\s*(?:Duration|Period)(?:[^\n]*\n){0,3}?[^\n]*?(\d[^\n]*)", pdf_text, re.I)
    if m: r["contract_dur"] = m.group(1).strip()

    # Evaluation method
    m = re.search(r"Evaluation\s*Method\s*[:\n]\s*(.+)", pdf_text, re.I)
    if m: r["eval_method"] = m.group(1).strip()

    # Bid type
    m = re.search(r"Type\s*of\s*Bid\s*[:\n]\s*(.+)", pdf_text, re.I)
    if m: r["bid_type"] = m.group(1).strip()

    # Bid to RA
    m = re.search(r"Bid\s*to\s*RA\s*(?:enabled)?\s*[:\n]\s*(\S+)", pdf_text, re.I)
    if m: r["bid_to_ra"] = m.group(1).strip()

    return r


def extract_consignee_location(pdf_text: str) -> dict:
    """
    Extract the consignee delivery address and pincode.
    Returns {"location": "..."}
    """
    r = {}
    lower = pdf_text.lower()

    # Find the consignee section header
    table_pos = -1
    for marker in ["/consignees/reporting officer", "reporting/officer and quantity",
                   "consignee\nreporting/officer"]:
        p = lower.find(marker)
        if p != -1:
            table_pos = p
            break

    if table_pos == -1:
        idx = 0
        while True:
            p = lower.find("consignee", idx)
            if p == -1: break
            pre = lower[max(0, p - 60): p]
            post = lower[p: p + 80]
            if re.search(r'(wise|method|evaluation|item|-)[\s]*$', pre) or \
               re.search(r'^consignee\s+(wise|location\b|combination)', post):
                idx = p + 1
                continue
            table_pos = p
            break

    if table_pos == -1:
        # Last resort: extract city from schedule table pattern
        m = re.search(r'Schedule\s+\d+\s*\([\s]*([A-Z][A-Z ]+[A-Z])[\s]*\)', pdf_text)
        if m:
            r["location"] = m.group(1).strip()
        return r

    sub = pdf_text[table_pos:]

    # Find first pincode line
    pin_m = re.search(r'\b(\d{6})\s*,\s*(\S[^\n]*)', sub)
    if pin_m:
        pincode = pin_m.group(1).strip()
        address_part = pin_m.group(2).strip()
        
        # Clean trailing numeric columns (e.g. ", 5, 90" representing Quantity and Delivery Days)
        parts = [p.strip() for p in address_part.split(",")]
        # Drop trailing items that are purely numeric
        while parts and parts[-1].isdigit():
            parts.pop()
        
        cleaned_address = f"{pincode}, " + ", ".join(parts) if parts else pincode
        loc_parts = [cleaned_address]
        
        after = sub[pin_m.end():]
        for ln in after.splitlines():
            c = ln.strip()
            if not c: continue
            cl = c.lower()
            if c.isdigit(): break
            if c.lower().startswith("advisory") or "buyer added" in cl: break
            if c.startswith("/") or "technical specifications" in cl: break
            if "bill of quantities" in cl or "schedule of requirement" in cl or "boq" in cl: break
            if re.match(r'^\d{6}\s*,', c): break
            loc_parts.append(c)
        r["location"] = " ".join(loc_parts).strip()


    else:
        # Fallback: collect lines that look like an address
        sub_lines = sub.splitlines()
        skip_kws = {"consignee", "reporting", "officer", "s.n", "delivery", "days",
                    "quantity", "estimated", "requirement", "address",
                    "to be set", "product", "number", "service", "period", "months"}
        addr_lines = []
        started = False
        for ln in sub_lines:
            c = ln.strip()
            if not c: continue
            cl = c.lower()
            if "buyer added" in cl or "disclaimer" in cl or cl.startswith("advisory"): break
            ascii_ratio = sum(1 for ch in c if ord(ch) < 128) / max(len(c), 1)
            if ascii_ratio < 0.5: continue
            stripped = re.sub(r'^[\*\-\.]+', '', c).strip()
            if stripped: c = stripped
            cl = c.lower()
            if not started:
                if any(kw in cl for kw in skip_kws) or c.startswith("/"): continue
                if c.isdigit(): continue
                words = c.split()
                if all(w and w[0].isupper() for w in words) and len(words) <= 3: continue
                started = True
                addr_lines.append(c)
            else:
                if c.isdigit(): break
                addr_lines.append(c)
        if addr_lines:
            r["location"] = " ".join(addr_lines).strip()

    return r


def extract_boq_table(pdf_text: str) -> dict:
    """
    Extract Bill of Quantities (BOQ) / Schedule of Rates as a list of line items.
    Returns {"boq": [{"item": ..., "qty": ..., "unit": ..., "rate": ...}, ...]}
    """
    boq_items = []

    # Find BOQ/schedule section
    boq_pos = -1
    for marker in ["bill of quantities", "schedule of rates", "boq",
                   "schedule of requirement", "item/category"]:
        p = pdf_text.lower().find(marker)
        if p != -1:
            boq_pos = p
            break

    if boq_pos == -1:
        return {"boq": boq_items}

    sub = pdf_text[boq_pos: boq_pos + 4000]

    # Parse rows: lines that start with a number, item description, qty, unit
    for line in sub.splitlines():
        line = line.strip()
        if not line:
            continue
        # Match pattern: <number> <description> <qty> <unit> [rate]
        m = re.match(
            r"(\d+)\s+(.{5,80}?)\s+(\d[\d,\.]*)\s+(Nos?\.?|Kg|MT|Ltr?|Set|Pair|M|Mtr|Unit|RM|Sqm|Cum)\b",
            line, re.I
        )
        if m:
            boq_items.append({
                "sno": m.group(1),
                "item": m.group(2).strip(),
                "qty": m.group(3).replace(",", ""),
                "unit": m.group(4),
            })
        if len(boq_items) >= 50:  # cap to avoid oversized payloads
            break

    return {"boq": boq_items}


def compare_with_previous_bid(bid_no_prefix: str) -> dict:
    """
    Look up a previous tender in the SQLite database with a similar bid number
    prefix (e.g. same department + similar item).
    Returns the most recent matching record or an empty dict.
    """
    try:
        import db
        all_tenders = db.load_all_tenders()
        prefix = bid_no_prefix.strip().upper()

        # Match by bid_no prefix (same year/type) or department keywords
        candidates = [
            t for t in all_tenders
            if t.get("bid_no", "").startswith(prefix[:12])  # e.g. "GEM/2026/B/"
        ]
        if not candidates:
            return {"previous_bid": None, "message": "No previous similar bid found."}

        # Return the most recent (assume higher bid_no = more recent)
        candidates.sort(key=lambda x: x.get("bid_no", ""), reverse=True)
        prev = candidates[0]
        return {
            "previous_bid": {
                k: prev.get(k)
                for k in ["bid_no", "dept", "items", "category", "est_value",
                           "location", "min_turnover", "exp_years", "emd", "epbg"]
            }
        }
    except Exception as e:
        logger.log("warn", f"compare_with_previous_bid failed: {e}")
        return {"previous_bid": None, "error": str(e)}


def lookup_product_match(item_description: str) -> dict:
    """
    Match the item description against the company product database.
    Returns {"matched_products": [...], "match_score": float}
    """
    try:
        import db
        products = db.load_all_products()
        desc_lower = item_description.lower()
        matched = []
        for p in products:
            name = p.get("name", "").lower()
            desc = p.get("description", "").lower()
            if name in desc_lower or desc_lower in name or desc in desc_lower:
                matched.append(p.get("name", ""))
        score = min(1.0, len(matched) / max(1, len(products) * 0.3)) if matched else 0.0
        return {"matched_products": matched, "match_score": round(score, 2)}
    except Exception as e:
        logger.log("warn", f"lookup_product_match failed: {e}")
        return {"matched_products": [], "match_score": 0.0, "error": str(e)}


def search_pdf_section(pdf_text: str, section_name: str) -> dict:
    """
    Locate and return a specific named section from the full PDF text.
    Useful for extracting Technical Specifications, Terms & Conditions,
    Annexures, etc.
    """
    try:
        from pdf_extractor import extract_section
        content = extract_section(pdf_text, section_name)
        return {
            "section_name": section_name,
            "content": content if content else f"Section '{section_name}' not found in document.",
        }
    except Exception as e:
        return {"section_name": section_name, "content": "", "error": str(e)}


# ---------------------------------------------------------------------------
# Tool Registry — maps tool name → (function, JSON schema)
# ---------------------------------------------------------------------------

TOOL_REGISTRY: dict = {
    "extract_bid_metadata": extract_bid_metadata,
    "extract_department_info": extract_department_info,
    "extract_eligibility_criteria": extract_eligibility_criteria,
    "extract_financial_security": extract_financial_security,
    "extract_item_details": extract_item_details,
    "extract_consignee_location": extract_consignee_location,
    "extract_boq_table": extract_boq_table,
    "compare_with_previous_bid": compare_with_previous_bid,
    "lookup_product_match": lookup_product_match,
    "search_pdf_section": search_pdf_section,
}

# JSON schemas for each tool (OpenAI / LM Studio compatible)
TOOL_SCHEMAS: list = [
    {
        "type": "function",
        "function": {
            "name": "extract_bid_metadata",
            "description": "Extract core bid identification: bid_no, bid_url, start_date, end_date, bid_opening, est_value from GeM tender PDF text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pdf_text": {"type": "string", "description": "Full raw text of the tender PDF."}
                },
                "required": ["pdf_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "extract_department_info",
            "description": "Extract ministry, department name, organisation, and office from tender PDF text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pdf_text": {"type": "string", "description": "Full raw text of the tender PDF."}
                },
                "required": ["pdf_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "extract_eligibility_criteria",
            "description": "Extract eligibility criteria: min_turnover, exp_years, MII compliance, MSE preferences, startup relaxation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pdf_text": {"type": "string", "description": "Full raw text of the tender PDF."}
                },
                "required": ["pdf_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "extract_financial_security",
            "description": "Extract EMD (Earnest Money Deposit) and ePBG (Performance Bank Guarantee) requirements and amounts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pdf_text": {"type": "string", "description": "Full raw text of the tender PDF."}
                },
                "required": ["pdf_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "extract_item_details",
            "description": "Extract item/category, quantity, contract duration, evaluation method, bid type, and Bid-to-RA.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pdf_text": {"type": "string", "description": "Full raw text of the tender PDF."}
                },
                "required": ["pdf_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "extract_consignee_location",
            "description": "Extract the consignee delivery address including pincode from the tender PDF.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pdf_text": {"type": "string", "description": "Full raw text of the tender PDF."}
                },
                "required": ["pdf_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "extract_boq_table",
            "description": "Extract Bill of Quantities (BOQ) or Schedule of Rates as a structured list of items with quantity and unit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pdf_text": {"type": "string", "description": "Full raw text of the tender PDF."}
                },
                "required": ["pdf_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_with_previous_bid",
            "description": "Look up a previous similar tender in the local database to detect deviations in terms, values, or requirements.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bid_no_prefix": {
                        "type": "string",
                        "description": "The bid number prefix to search (e.g. 'GEM/2026/B/' to find all 2026 bids)."
                    }
                },
                "required": ["bid_no_prefix"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_product_match",
            "description": "Match the tender item description against the company's product database to check eligibility.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_description": {
                        "type": "string",
                        "description": "The item or product description from the tender."
                    }
                },
                "required": ["item_description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_pdf_section",
            "description": "Find and return a specific named section from the PDF (e.g. 'Technical Specifications', 'Annexure', 'Terms and Conditions').",
            "parameters": {
                "type": "object",
                "properties": {
                    "pdf_text": {"type": "string", "description": "Full raw text of the tender PDF."},
                    "section_name": {"type": "string", "description": "Name of the section to locate (e.g. 'Technical Specifications')."}
                },
                "required": ["pdf_text", "section_name"]
            }
        }
    },
]


def execute_tool(tool_name: str, tool_args: dict) -> str:
    """
    Execute a tool by name with the given arguments dict.
    Returns the result serialized as a JSON string.
    """
    fn = TOOL_REGISTRY.get(tool_name)
    if fn is None:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    try:
        result = fn(**tool_args)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        logger.log("warn", f"Tool '{tool_name}' execution failed: {e}")
        return json.dumps({"error": str(e)})
