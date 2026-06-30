import re

def split_blocks(text):
    parts = re.split(r'(?=BID\s*(?:NO|Number)(?:\.|\b)\s*:)', text, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]

def parse_one(text):
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

    return r

def convert_pdf_text_to_markdown(pdf_text):
    # 1. Bid Number
    bid_no = re.search(r"Bid\s*Number\s*(?::|\n)\s*(\S+)", pdf_text, re.I)
    if not bid_no:
        bid_no = re.search(r"BID\s*NO(?:\.|\b)\s*(?::|\n)\s*(\S+)", pdf_text, re.I)

    # 2. Item Category
    item_cat = re.search(r"Item\s*Category\s*(?::|\n)\s*(.+)", pdf_text, re.I)

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
    location = ""
    idx = pdf_text.lower().find("consignee")
    if idx == -1:
        idx = pdf_text.lower().find("reporting/officer")
    if idx == -1:
        idx = pdf_text.lower().find("/address")
        
    if idx != -1:
        sub = pdf_text[idx:]
        sub_lines = sub.splitlines()
        start_idx = 0
        for i, line in enumerate(sub_lines):
            cleaned = line.strip()
            if cleaned == "1":
                start_idx = i + 1
                break
        else:
            header_keywords = [
                "consignee", "reporting", "officer", "address", "estimated", "quantity", 
                "requirement", "परे षती", "Tरपो@टgग", "अिधकार", "पता", "संसाधन", "मात्रा", 
                "अतिरिक्त", "आवश्यकता", "=.सं.", "s.n", "o."
            ]
            for i, line in enumerate(sub_lines):
                cleaned = line.strip().lower()
                if not cleaned:
                    continue
                is_header = any(kw in cleaned for kw in header_keywords)
                if not is_header:
                    start_idx = i
                    break
                    
        data_lines = []
        for line in sub_lines[start_idx:]:
            cleaned = line.strip()
            if not cleaned:
                continue
            if cleaned in ("2", "3", "4", "5") or "buyer added" in cleaned.lower() or "disclaimer" in cleaned.lower():
                break
            data_lines.append(cleaned)
            
        qty_idx = -1
        for i in range(len(data_lines) - 1, -1, -1):
            if data_lines[i].isdigit():
                qty_idx = i
                break
                
        # Use whole word boundary check to avoid false matches on names like Narendra
        if qty_idx == -1:
            for idx_d, line in enumerate(data_lines):
                cleaned_line = line.lower()
                if re.search(r'\b(?:na|n/a|lumpsum|project|based|quantity)\b', cleaned_line):
                    qty_idx = idx_d
                    break
                    
        if qty_idx != -1:
            row_content_lines = data_lines[:qty_idx]
            addr_start_idx = -1
            for idx_c, line in enumerate(row_content_lines):
                if re.search(r'\b\d{6}\b', line):
                    addr_start_idx = idx_c
                    break
                cleaned_line = line.lower()
                if "address" in cleaned_line or "pin code" in cleaned_line or "pincode" in cleaned_line:
                    addr_start_idx = idx_c
                    break
            if addr_start_idx == -1:
                if len(row_content_lines) > 2:
                    addr_start_idx = 2
                else:
                    addr_start_idx = min(1, len(row_content_lines))
            location = " ".join(row_content_lines[addr_start_idx:]).strip()

    lines = []
    if bid_no:
        lines.append(f"BID NO: {bid_no.group(1).strip()}")
    if item_cat:
        lines.append(f"Items: {item_cat.group(1).strip()}")
        lines.append(f"Category: {item_cat.group(1).strip()}")
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
        lines.append(f"Location: {location}")
        
    return "\n".join(lines)
