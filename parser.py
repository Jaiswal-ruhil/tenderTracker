import re

def split_blocks(text):
    parts = re.split(r'(?=BID\s*NO(?:\.|\b)\s*:)', text, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]

def parse_one(text):
    r = {}
    m = re.search(r"BID\s*NO(?:\.|\b)\s*:\s*\[([^\]]+)\]\((https?://[^)]+)\)", text, re.I)
    if m:
        r["bid_no"]=m.group(1).strip(); r["bid_url"]=m.group(2).strip()
    else:
        m2 = re.search(r"BID\s*NO(?:\.|\b)\s*:\s*(.+)", text, re.I)
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
                r["bid_url"] = f"https://bidplus.gem.gov.in/showbiddocument/{id_match.group(1)}"
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
    return r
