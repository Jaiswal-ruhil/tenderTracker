import re
try:
    from geocode import enrich_location as _enrich_location
except ImportError:  # geocode not available (e.g. build environment)
    def _enrich_location(loc): return loc

try:
    from config import CATEGORY_MAPPING
except ImportError:
    CATEGORY_MAPPING = []

def map_category(raw_val):
    if not raw_val or not str(raw_val).strip():
        return ""
    val_lower = str(raw_val).lower()
    
    # Try loading from settings
    try:
        import db
        settings = db.load_settings()
        mappings = settings.get("category_mappings")
    except Exception:
        mappings = None
        settings = {}
        
    if not mappings:
        # Fallback to config
        try:
            from config import CATEGORY_MAPPING
            mappings = [{"name": val, "keywords": kws} for kws, val in CATEGORY_MAPPING]
        except ImportError:
            mappings = []
            
    # LLM category mapping if enabled
    try:
        use_llm = settings.get("llm_use_mapping", False)
        provider = settings.get("llm_provider", "Disabled")
        if use_llm and provider != "Disabled":
            existing_categories = [m["name"] for m in mappings if m.get("name")]
            import llm
            api_key = settings.get("llm_api_key", "")
            base_url = settings.get("llm_base_url", "")
            model = settings.get("llm_model", "")
            mapped_val = llm.llm_map_category(raw_val, existing_categories, provider, api_key, base_url, model)
            if mapped_val:
                return mapped_val
    except Exception as e:
        import logger
        logger.log("warn", f"LLM category mapping failed: {e}. Falling back to keyword mapping.")

    # Fallback to keyword matching
    for item in mappings:
        keywords = item.get("keywords", [])
        standard_name = item.get("name", "")
        if keywords and standard_name:
            if all(kw.lower() in val_lower for kw in keywords):
                return standard_name
                
    return raw_val.strip().title()


def _is_mapped_category(category_name):
    """
    Returns True if category_name is a known entry in the category_mappings
    settings (i.e. it was resolved by the mapper, not just raw-title-cased).
    """
    if not category_name or not str(category_name).strip():
        return False
    try:
        import db
        settings = db.load_settings()
        mappings = settings.get("category_mappings")
        if not mappings:
            from config import CATEGORY_MAPPING
            mappings = [{"name": val, "keywords": kws} for kws, val in CATEGORY_MAPPING]
        known_names = {m["name"].lower() for m in mappings if m.get("name")}
        return category_name.strip().lower() in known_names
    except Exception:
        return False


def assign_tender_status(record):
    """
    Auto-assign filing_status based on whether the category matched a known
    mapping rule.  Never overwrites an existing 'Filed' status — that guard
    lives in db.py during upsert.

    Returns the (possibly modified) record.
    """
    category = record.get("category", "")
    if _is_mapped_category(category):
        record.setdefault("filing_status", "To Be Filed")
        if record.get("filing_status") not in ("Filed", "To Be Filed", "Evaluating"):
            record["filing_status"] = "To Be Filed"
        elif record.get("filing_status") == "":
            record["filing_status"] = "To Be Filed"
    else:
        record.setdefault("filing_status", "Evaluating")
        if record.get("filing_status") not in ("Filed", "To Be Filed", "Evaluating"):
            record["filing_status"] = "Evaluating"
        elif record.get("filing_status") == "":
            record["filing_status"] = "Evaluating"
    return record


def split_blocks(text):
    parts = re.split(r'(?=BID\s*(?:NO|Number)(?:\.|\b)\s*:)', text, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]

def parse_one(text):
    # LLM Parsing as primary (if provider is configured)
    try:
        import db
        settings = db.load_settings()
        provider = settings.get("llm_provider", "Disabled")
        if provider != "Disabled":
            import llm
            api_key = settings.get("llm_api_key", "")
            base_url = settings.get("llm_base_url", "")
            model = settings.get("llm_model", "")
            parsed = llm.llm_parse_tender(text, provider, api_key, base_url, model)
            if parsed and isinstance(parsed, dict) and parsed.get("bid_no"):
                # Enrich location if it exists
                if parsed.get("location"):
                    parsed["location"] = _enrich_location(parsed["location"])
                
                # Apply standard category mapping to parsed category field
                if parsed.get("category"):
                    parsed["category"] = map_category(parsed["category"])
                
                # Apply custom value mappings
                try:
                    parsed = db.apply_value_mappings(parsed)
                except Exception:
                    pass
                # Auto-assign tender status based on mapped category
                parsed = assign_tender_status(parsed)
                return parsed
            else:
                import logger
                logger.log("warn", "LLM parser returned empty or invalid data. Falling back to regex parser.")
    except Exception as e:
        import logger
        logger.log("warn", f"LLM parsing failed: {e}. Falling back to regex parser.")

    r = {}
    m = re.search(r"BID\s*(?:NO|Number)(?:\.|\b)\s*:\s*\[([^\]]+)\]\((https?://[^)]+)\)", text, re.I)
    if m:
        r["bid_no"]=m.group(1).strip(); r["bid_url"]=m.group(2).strip()
    else:
        m2 = re.search(r"BID\s*(?:NO|Number)(?:\.|\b)\s*:\s*(.+)", text, re.I)
        if m2: r["bid_no"]=m2.group(1).strip()

    # Clean up bid_no if it contains extra text (e.g., "View Corrigendum")
    if "bid_no" in r:
        bid_no_match = re.search(r"(GEM/\d{4}/[A-Z0-9]+/\d+)", r["bid_no"], re.I)
        if bid_no_match:
            r["bid_no"] = bid_no_match.group(1).strip()

    # Try to find a URL in the text if it wasn't matched above,
    # or construct it from the bid number ID.
    if "bid_no" in r and "bid_url" not in r:
        url_match = re.search(r"(https?://[^\s\)\"\'\>]+)", text, re.I)
        if url_match:
            r["bid_url"] = url_match.group(1).strip()
        else:
            id_match = re.search(r"(\d+)$", r["bid_no"])
            if id_match:
                r["bid_url"] = f"https://bidplus.gem.gov.in/showbidDocument/{id_match.group(1)}"
    m=re.search(r"Items?\s*:\s*(.+)", text, re.I)
    if m: r["items"]=m.group(1).strip()
    m=re.search(r"Quantit[yi]\w*\s*:\s*(\S+)", text, re.I)
    if m: r["quantity"]=m.group(1).strip()
    m=re.search(r"Department\s*(?:Name\s*(?:And\s*Address)?)?\s*:\s*\n(.*?)(?=\n[A-Z]|\Z)", text, re.I|re.DOTALL)
    if m:
        for ln in m.group(1).splitlines():
            ln=ln.strip()
            if ln: r["dept"]=ln; break
    m=re.search(r"Start\s*Date\s*:\s*(.+)", text, re.I)
    if m: r["start_date"]=m.group(1).strip()
    m=re.search(r"End\s*Date\s*:\s*(.+)", text, re.I)
    if m: r["end_date"]=m.group(1).strip()
    m = re.search(r"Bid\s*Opening\s*(?:Date)?\s*:\s*(.+)", text, re.I)
    if m: r["bid_opening"] = m.group(1).strip()

    # Detailed fields parsing
    m = re.search(r"Ministry\s*:\s*(.+)", text, re.I)
    if m: r["ministry"] = m.group(1).strip()
    m = re.search(r"Organisation\s*:\s*(.+)", text, re.I)
    if m: r["organisation"] = m.group(1).strip()
    m = re.search(r"Office\s*:\s*(.+)", text, re.I)
    if m: r["office"] = m.group(1).strip()
    m = re.search(r"Category\s*:\s*(.+)", text, re.I)
    if m: r["category"] = m.group(1).strip()
    m = re.search(r"Estimated\s*Value\s*(?:\(Rs\))?\s*:\s*(\S+)", text, re.I)
    if m: r["est_value"] = m.group(1).strip()
    m = re.search(r"Evaluation\s*Method\s*:\s*(.+)", text, re.I)
    if m: r["eval_method"] = m.group(1).strip()
    m = re.search(r"Bid\s*Type\s*:\s*(.+)", text, re.I)
    if m: r["bid_type"] = m.group(1).strip()
    m = re.search(r"Bid\s*to\s*RA\s*:\s*(\S+)", text, re.I)
    if m: r["bid_to_ra"] = m.group(1).strip()
    m = re.search(r"EMD\s*Required\s*:\s*(\S+)", text, re.I)
    if m: r["emd"] = m.group(1).strip()
    m = re.search(r"ePBG\s*Required\s*:\s*(\S+)", text, re.I)
    if m: r["epbg"] = m.group(1).strip()
    m = re.search(r"MII\s*Compliance\s*:\s*(\S+)", text, re.I)
    if m: r["mii"] = m.group(1).strip()
    m = re.search(r"MSE\s*Purchase\s*Preference\s*:\s*(\S+)", text, re.I)
    if m: r["mse_pref"] = m.group(1).strip()
    m = re.search(r"MSE\s*Relaxation\s*:\s*(\S+)", text, re.I)
    if m: r["mse_relax"] = m.group(1).strip()
    m = re.search(r"Startup\s*Relaxation\s*:\s*(\S+)", text, re.I)
    if m: r["startup_relax"] = m.group(1).strip()
    m = re.search(r"Min\s*Turnover\s*(?:\(Lakhs\))?\s*:\s*(.+)", text, re.I)
    if m: r["min_turnover"] = m.group(1).strip()
    m = re.search(r"Experience\s*Required\s*(?:\(Yrs\))?\s*:\s*(.+)", text, re.I)
    if m: r["exp_years"] = m.group(1).strip()
    m = re.search(r"Contract\s*Duration\s*:\s*(.+)", text, re.I)
    if m: r["contract_dur"] = m.group(1).strip()
    m = re.search(r"Location\s*:\s*(.+)", text, re.I)
    if m: r["location"] = m.group(1).strip()

    if "category" in r:
        raw_cat = r["category"]
        if "-" in raw_cat:
            parts = re.split(r"\s*-\s*", raw_cat, maxsplit=1)
            cat_part = parts[0].strip()
            item_part = parts[1].strip()
        else:
            cat_part = raw_cat
            item_part = raw_cat
            
        mapped_cat = map_category(raw_cat)
        if mapped_cat != raw_cat.strip().title():
            r["category"] = mapped_cat
        else:
            r["category"] = map_category(cat_part)
            
        if "items" not in r:
            r["items"] = item_part
    elif "items" in r:
        r["category"] = map_category(r["items"])

    # Apply custom field value mappings
    try:
        import db
        r = db.apply_value_mappings(r)
    except Exception:
        pass

    # Auto-assign tender status based on whether category was mapped
    r = assign_tender_status(r)

    # Warn if the regex parser failed to extract a valid bid number
    has_bid = r.get("bid_no") and re.match(r"^GEM/\d{4}/[A-Z0-9]+/\d+$", r["bid_no"], re.I)
    if not has_bid:
        import logger
        logger.log("warn", "Regex parsing failed to find a valid bid number.")

    return r

def convert_pdf_text_to_markdown(pdf_text):
    # 1. Bid Number
    bid_no = re.search(r"Bid\s*Number\s*(?::|\n)\s*(\S+)", pdf_text, re.I)
    if not bid_no:
        bid_no = re.search(r"BID\s*NO(?:\.|\b)\s*(?::|\n)\s*(\S+)", pdf_text, re.I)

    # 2. Item Category (with multi-line and fallback support)
    item_cat_val = ""
    pos = re.search(r"Item\s*Category\s*(?::|\n)\s*", pdf_text, re.I)
    if pos:
        sub = pdf_text[pos.end():pos.end()+500]
        val_parts = []
        headers = ["ministry", "department", "organisation", "office", "dated", "bid end", "bid opening", "estimated", "evaluation", "type of", "consignee", "reporting"]
        for line in sub.splitlines():
            line_clean = line.strip()
            if not line_clean:
                continue
            if line_clean.startswith("/") or line_clean.startswith("*"):
                break
            if any(h in line_clean.lower() for h in headers):
                break
            if ":" in line_clean and re.match(r"^[A-Za-z0-9/\s]+:", line_clean):
                break
            ascii_ratio = sum(1 for c in line_clean if ord(c) < 128) / len(line_clean)
            if ascii_ratio < 0.5:
                break
            val_parts.append(line_clean)
        item_cat_val = " ".join(val_parts).strip()
        
    if not item_cat_val:
        # Fallback to Core Category
        pos_core = re.search(r"Core", pdf_text, re.I)
        if pos_core:
            sub = pdf_text[pos_core.end():pos_core.end()+500]
            lines_core = sub.splitlines()
            for idx, line in enumerate(lines_core):
                if "category" in line.lower() and idx + 1 < len(lines_core):
                    line_next = lines_core[idx+1].strip()
                    if line_next and not line_next.startswith("/") and not line_next.startswith("*"):
                        ascii_ratio = sum(1 for c in line_next if ord(c) < 128) / len(line_next)
                        if ascii_ratio >= 0.5:
                            item_cat_val = line_next
                            break

    # 3. Quantity
    qty = re.search(r"Total\s*Quantity\s*(?::|\n)\s*(\d+)", pdf_text, re.I)
    if not qty:
        qty = re.search(r"Quantity\s*(?::|\n)\s*(\d+)", pdf_text, re.I)
    if not qty:
        idx = pdf_text.lower().find("consignee")
        if idx != -1:
            sub = pdf_text[idx:]
            m = re.search(r"\n\s*(\d+)\s*\n\s*(?:N/A|NA)", sub, re.I)
            if m:
                qty = m

    # 4. Department
    dept = re.search(r"Department\s*Name\s*(?::|\n)\s*([\s\S]*?)(?=\n(?:संगठन|Organisation|\Z))", pdf_text, re.I)
    if not dept:
        dept = re.search(r"Department\s*Name\s*(?::|\n)\s*(.+)", pdf_text, re.I)

    # 5. Start Date (Dated)
    start = re.search(r"Dated\s*(?::|\n)\s*([0-9]{2}-[0-9]{2}-[0-9]{4})", pdf_text, re.I)
    if not start:
        start = re.search(r"Bid\s*Start\s*Date\s*(?:/\s*Time)?\s*(?::|\n)\s*([0-9]{2}-[0-9]{2}-[0-9]{4})", pdf_text, re.I)

    # 6. End Date
    end = re.search(r"Bid\s*End\s*Date\s*(?:/\s*Time)?\s*(?::|\n)\s*([0-9]{2}-[0-9]{2}-[0-9]{4}[^\n]*)", pdf_text, re.I)
    
    # 7. Bid Opening Date
    bid_opening = re.search(r"Bid\s*Opening\s*(?:\n|Date/Time|\s|/)*\s*([0-9]{2}[-/][0-9]{2}[-/][0-9]{4}[^\n]*)", pdf_text, re.I)
    
    # Extra PDF details
    ministry = re.search(r"Ministry/State\s*Name\s*(?::|\n)\s*(.+)", pdf_text, re.I)
    org = re.search(r"Organisation\s*Name\s*(?::|\n)\s*(.+)", pdf_text, re.I)
    office = re.search(r"Office\s*Name\s*(?::|\n)\s*(.+)", pdf_text, re.I)
    
    # Line limited regexes to prevent matching far-away numbers when fields are not present/N/A
    est_val = re.search(r"Estimated\s*Bid\s*Value(?:[^\n]*\n){0,3}?[^\n]*?(\d+)", pdf_text, re.I)
    eval_method = re.search(r"Evaluation\s*Method\s*(?::|\n)\s*(.+)", pdf_text, re.I)
    bid_type = re.search(r"Type\s*of\s*Bid\s*(?::|\n)\s*(.+)", pdf_text, re.I)
    bid_to_ra = re.search(r"Bid\s*to\s*RA\s*(?:enabled)?\s*(?::|\n)\s*(\S+)", pdf_text, re.I)
    
    # EMD & ePBG block division to avoid section cross-talk
    emd_block = ""
    epbg_block = ""
    emd_idx = pdf_text.lower().find("emd detail")
    epbg_idx = pdf_text.lower().find("epbg detail")
    if emd_idx != -1:
        if epbg_idx != -1 and epbg_idx > emd_idx:
            emd_block = pdf_text[emd_idx:epbg_idx]
            epbg_block = pdf_text[epbg_idx:epbg_idx + 1000]
        else:
            emd_block = pdf_text[emd_idx:emd_idx + 1000]
            
    emd_required_val = "No"
    if emd_block:
        if "advisory bank" in emd_block.lower() or "emd amount" in emd_block.lower() or "amount" in emd_block.lower():
            emd_required_val = "Yes"
        elif re.search(r"Required\s*(?::|\n)\s*Yes", emd_block, re.I):
            emd_required_val = "Yes"
            
    epbg_required_val = "No"
    if epbg_block:
        m_req = re.search(r"Required\s*(?::|\n)\s*(Yes|No)", epbg_block, re.I)
        if m_req:
            epbg_required_val = m_req.group(1).strip()
        elif "advisory bank" in epbg_block.lower() or "duration" in epbg_block.lower():
            epbg_required_val = "Yes"

    mii = re.search(r"MII\s*Compliance(?:[^\n]*\n){0,3}?[^\n]*?(Yes|No)", pdf_text, re.I)
    mse_pref = re.search(r"MSE\s*Purchase\s*Preference(?:[^\n]*\n){0,3}?[^\n]*?(Yes|No)", pdf_text, re.I)
    mse_relax = re.search(r"MSE\s*Relaxation(?:[^\n]*\n){0,3}?[^\n]*?(Yes|No)", pdf_text, re.I)
    startup_relax = re.search(r"Startup\s*Relaxation(?:[^\n]*\n){0,3}?[^\n]*?(Yes|No)", pdf_text, re.I)
    
    min_turnover = re.search(r"Minimum\s*Average\s*Annual\s*Turnover(?:[^\n]*\n){0,3}?[^\n]*?(?<!For\s)(?<!For\s\s)([0-9][^\n]*)", pdf_text, re.I)
    exp_years = re.search(r"Years\s*of\s*Past\s*Experience(?:[^\n]*\n){0,3}?[^\n]*?(?<!For\s)(?<!For\s\s)([0-9][^\n]*)", pdf_text, re.I)
    contract_dur = re.search(r"Contract\s*(?:Duration|Period)(?:[^\n]*\n){0,3}?[^\n]*?([0-9][^\n]*)", pdf_text, re.I)

    # Consignee / Delivery Location
    # Strategy: find the consignee TABLE header, then collect the first
    # pincode,Name ... City entry, stopping at the quantity (digit-only line).
    location = ""
    # Prefer the specific consignee table header over a generic "consignee" mention.
    # We MUST skip false positives like "consignee wise evaluation" which appear in
    # the evaluation-method description, not in the actual consignee address section.
    table_pos = -1
    _lower = pdf_text.lower()

    # Phase 1 – look for unambiguous section headers (highest confidence)
    for marker in ["/consignees/reporting officer", "reporting/officer and quantity",
                   "consignee\nreporting/officer", "consignee reporting/officer"]:
        p = _lower.find(marker)
        if p != -1:
            table_pos = p
            break

    # Phase 2 – fallback: find "consignee" but skip occurrences that are clearly
    # inside an evaluation-method phrase (e.g. "consignee wise evaluation") or
    # a cross-reference clause (e.g. "details of item-consignee combination").
    if table_pos == -1:
        idx = 0
        while True:
            p = _lower.find("consignee", idx)
            if p == -1:
                break
            # Grab up to 60 chars before this occurrence to check context
            pre = _lower[max(0, p - 60):p]
            post = _lower[p:p + 80]
            # Skip if it looks like an evaluation-method phrase or a cross-ref
            if re.search(r'(wise|method|evaluation|item|-)\s*$', pre) or \
               re.search(r'^consignee\s+(wise|location\b|combination)', post):
                idx = p + 1
                continue
            table_pos = p
            break

    # Phase 3 – other fallback markers
    if table_pos == -1:
        for marker in ["reporting/officer", "/address"]:
            p = _lower.find(marker)
            if p != -1:
                table_pos = p
                break

    if table_pos != -1:
        sub = pdf_text[table_pos:]
        # Find first pincode,Name line (6 digits followed by comma and any char)
        pin_m = re.search(r'\b(\d{6})\s*,\s*(\S[^\n]*)', sub)
        if pin_m:
            # Start location with the pincode and name on the same line
            loc_parts = [pin_m.group(0).strip()]
            after = sub[pin_m.end():]
            for ln in after.splitlines():
                cleaned = ln.strip()
                if not cleaned:
                    continue
                # Stop at digit-only line (quantity), technical spec markers, or advisory
                if cleaned.isdigit():
                    break
                if cleaned.lower().startswith("advisory") or "buyer added" in cleaned.lower():
                    break
                if cleaned.startswith("/") or "Technical Specifications" in cleaned:
                    break
                if re.match(r'^\d{6}\s*,', cleaned):
                    break  # Next consignee row starts
                loc_parts.append(cleaned)
            location = " ".join(loc_parts).strip()
        else:
            # Fallback for PDFs without a pincode: find address content by skipping
            # header lines (including Hindi/bilingual column headers and asterisk lines).
            sub_lines = sub.splitlines()
            skip_kws = {"consignee", "reporting", "officer", "s.n", "delivery", "days",
                        "quantity", "estimated", "requirement", "address", "पता",
                        "to be set", "product", "equipment", "additional", "number",
                        "service", "period", "months", "contract"}
            addr_lines = []
            addr_started = False
            for ln in sub_lines:
                cleaned = ln.strip()
                if not cleaned:
                    continue
                cl = cleaned.lower()
                # Hard stops
                if "buyer added" in cl or "disclaimer" in cl or cl.startswith("advisory"):
                    break
                # Skip lines that are mostly non-ASCII (Hindi/Devanagari column headers)
                ascii_ratio = sum(1 for c in cleaned if ord(c) < 128) / max(len(cleaned), 1)
                if ascii_ratio < 0.5:
                    continue
                # Skip lines that are all asterisks or similar punctuation (redacted fields)
                if re.match(r'^[\*\-\.\s]+$', cleaned):
                    continue
                # Lines like "***AGRA" or "***AGRA CITY" — strip leading punctuation
                stripped = re.sub(r'^[\*\-\.]+', '', cleaned).strip()
                if stripped:
                    cleaned = stripped
                cl = cleaned.lower()
                if not addr_started:
                    # Skip header-like lines and digit-only row numbers
                    if any(kw in cl for kw in skip_kws) or cleaned.startswith("/"):
                        continue
                    if cleaned.isdigit():
                        continue
                    # Skip pure column-header lines (all tokens start with uppercase, <= 3 words)
                    # UNLESS the line came from stripping asterisks (likely a real address token)
                    was_asterisk_prefixed = re.match(r'^[\*\-\.]+', ln.strip())
                    words = cleaned.split()
                    if not was_asterisk_prefixed and \
                       all(w and w[0].isupper() for w in words) and len(words) <= 3:
                        continue
                    # Any other substantial content starts the address
                    addr_started = True
                    addr_lines.append(cleaned)
                else:
                    if cleaned.isdigit():
                        break
                    addr_lines.append(cleaned)
            location = " ".join(addr_lines).strip()

    # Last resort: for BOQ-type PDFs where the consignee section lists city names
    # in a schedule table like "Schedule 1 ( LUCKNOW )" and no address block is
    # found via the methods above, extract the city from that pattern.
    # Also override if the fallback produced obviously wrong content (schedule item descriptions).
    _loc_lower = location.lower()
    location_looks_like_garbage = (
        not location or
        'schedule' in _loc_lower or
        'item/category' in _loc_lower or
        re.search(r'\d+\s*mm|\d+\s*ka|slab\s+\d', _loc_lower) is not None
    )
    if location_looks_like_garbage:
        sched_m = re.search(r'Schedule\s+\d+\s*\([\s]*([A-Z][A-Z ]+[A-Z])[\s]*\)', pdf_text)
        if sched_m:
            location = sched_m.group(1).strip()
        elif not location:
            pass  # leave empty



    lines = []
    if bid_no:
        lines.append(f"BID NO: {bid_no.group(1).strip()}")
    if item_cat_val:
        if "-" in item_cat_val:
            parts = re.split(r"\s*-\s*", item_cat_val, maxsplit=1)
            cat_part = parts[0].strip()
            item_part = parts[1].strip()
        else:
            cat_part = item_cat_val
            item_part = item_cat_val
        lines.append(f"Items: {item_part}")
        lines.append(f"Category: {map_category(cat_part)}")
    if qty:
        lines.append(f"Quantity: {qty.group(1).strip()}")
    if dept:
        lines.append(f"Department Name And Address:\n{dept.group(1).strip()}")
    if start:
        lines.append(f"Start Date: {start.group(1).strip()}")
    if end:
        lines.append(f"End Date: {end.group(1).strip()}")
    if bid_opening:
        lines.append(f"Bid Opening Date: {bid_opening.group(1).strip()}")
    if ministry:
        lines.append(f"Ministry: {ministry.group(1).strip()}")
    if org:
        lines.append(f"Organisation: {org.group(1).strip()}")
    if office:
        lines.append(f"Office: {office.group(1).strip()}")
    if est_val:
        lines.append(f"Estimated Value (Rs): {est_val.group(1).strip()}")
    if eval_method:
        lines.append(f"Evaluation Method: {eval_method.group(1).strip()}")
    if bid_type:
        lines.append(f"Bid Type: {bid_type.group(1).strip()}")
    if bid_to_ra:
        lines.append(f"Bid to RA: {bid_to_ra.group(1).strip()}")
    lines.append(f"EMD Required: {emd_required_val}")
    lines.append(f"ePBG Required: {epbg_required_val}")
    if mii:
        lines.append(f"MII Compliance: {mii.group(1).strip()}")
    if mse_pref:
        lines.append(f"MSE Purchase Preference: {mse_pref.group(1).strip()}")
    if mse_relax:
        lines.append(f"MSE Relaxation: {mse_relax.group(1).strip()}")
    if startup_relax:
        lines.append(f"Startup Relaxation: {startup_relax.group(1).strip()}")
    if min_turnover:
        lines.append(f"Min Turnover (Lakhs): {min_turnover.group(1).strip()}")
    if exp_years:
        lines.append(f"Experience Required (Yrs): {exp_years.group(1).strip()}")
    if contract_dur:
        lines.append(f"Contract Duration: {contract_dur.group(1).strip()}")
    if location:
        location = _enrich_location(location)
        lines.append(f"Location: {location}")
        
    return "\n".join(lines)

def learn_category_mapping(items, new_category):
    if not items or not new_category:
        return
        
    new_cat_clean = new_category.strip()
    if not new_cat_clean:
        return

    # If LLM mapping is enabled, ask the LLM to normalize/suggest a canonical
    # category name for these items. This helps keep category names consistent.
    try:
        import db
        settings = db.load_settings()
        use_llm = settings.get("llm_use_mapping", False)
        provider = settings.get("llm_provider", "Disabled")
        if use_llm and provider != "Disabled":
            try:
                import llm as _llm
                api_key = settings.get("llm_api_key", "")
                base_url = settings.get("llm_base_url", "")
                model = settings.get("llm_model", "")
                # Ensure server is running (attempt auto-start if a start command is configured)
                start_cmd = settings.get("llm_start_cmd")
                try:
                    _llm.ensure_server_running(base_url, start_cmd)
                except Exception:
                    pass

                suggested = _llm.llm_map_category(items, [m.get("name") for m in mappings if m.get("name")], provider, api_key, base_url, model)
                if suggested and suggested.strip():
                    # Prefer LLM suggestion as canonical name
                    new_cat_clean = suggested.strip()

                # Ask LLM for suggested keywords to improve mapping
                try:
                    kws = _llm.suggest_category_keywords(items, provider, api_key, base_url, model)
                    if kws:
                        # Store suggestions in settings for user review instead of auto-merging
                        pending = settings.get("llm_pending_keyword_suggestions", {}) or {}
                        existing = pending.get(new_cat_clean, [])
                        for k in kws:
                            if k not in existing:
                                existing.append(k)
                        pending[new_cat_clean] = existing
                        db.save_setting("llm_pending_keyword_suggestions", pending)
                except Exception:
                    pass
            except Exception as e:
                import logger
                logger.log("warn", f"LLM category mapping failed: {e}. Falling back to keyword mapping.")
    except Exception:
        pass
        
    # Load mappings
    import db
    settings = db.load_settings()
    mappings = settings.get("category_mappings")
    if not mappings:
        try:
            from config import CATEGORY_MAPPING
            mappings = [{"name": val, "keywords": kws} for kws, val in CATEGORY_MAPPING]
        except Exception:
            mappings = []
            
    # Find or create category entry
    cat_entry = None
    for m in mappings:
        if m["name"].lower() == new_cat_clean.lower():
            cat_entry = m
            break
            
    if not cat_entry:
        cat_entry = {"name": new_cat_clean, "keywords": []}
        mappings.append(cat_entry)
        
    # Extract keywords from items description
    stop_words = {"and", "for", "with", "the", "by", "of", "in", "at", "on", "to", "from", "lumpsum", "basis", "qty", "detail", "required"}
    
    # Split items by non-alphanumeric chars
    words = re.findall(r"\b[A-Za-z]+\b", str(items).lower())
    
    clean_words = []
    for w in words:
        if len(w) >= 3 and w not in stop_words:
            clean_words.append(w)
            
    if not clean_words:
        return
        
    # Try to find a word that overlaps with category name first
    cat_words = re.findall(r"\b[A-Za-z]+\b", new_cat_clean.lower())
    candidate = None
    for w in clean_words:
        if w in cat_words or any(w in cw or cw in w for cw in cat_words):
            candidate = w
            break
            
    # Fallback to the first clean word if no overlap
    if not candidate:
        candidate = clean_words[0]
        
    if candidate and candidate not in cat_entry["keywords"]:
        cat_entry["keywords"].append(candidate)
        db.save_setting("category_mappings", mappings)
        import logger
        logger.log("info", f"Active Learning: Extracted keyword '{candidate}' for category '{new_cat_clean}' from items '{items}'")
