import os
import re
import pypdf
import json

mills = [
    "NAJIBABAD", "ANOOPSHAHR", "SULTANPUR", "NANPARA", "BELRAYAN",
    "SAMPURNANAGAR", "RAMALA", "MORNA", "GHOSI", "NANAUTA",
    "SEMIKHERA", "SARSAWAN", "MAHMUDABAD", "TILHAR", "BISALPUR",
    "POWAYAN", "PURANPUR", "BAGPAT", "GAJRAULLA", "FEDRATION",
    "CORPORATION", "KAIAMGANJ", "SATHIAON", "BUDAUN", "BILASPUR"
]

# Spelling variants mapping
mill_map = {
    "najibabad": "NAJIBABAD",
    "anoopshahr": "ANOOPSHAHR",
    "anupshahar": "ANOOPSHAHR",
    "anupshahr": "ANOOPSHAHR",
    "sultanpur": "SULTANPUR",
    "nanpara": "NANPARA",
    "belrayan": "BELRAYAN",
    "sampurnanagar": "SAMPURNANAGAR",
    "sampurna nagar": "SAMPURNANAGAR",
    "ramala": "RAMALA",
    "ramla": "RAMALA",
    "morna": "MORNA",
    "ghosi": "GHOSI",
    "nanauta": "NANAUTA",
    "semikhera": "SEMIKHERA",
    "semi khera": "SEMIKHERA",
    "sarsawan": "SARSAWAN",
    "mahmudabad": "MAHMUDABAD",
    "mahmoodabad": "MAHMUDABAD",
    "tilhar": "TILHAR",
    "bisalpur": "BISALPUR",
    "powayan": "POWAYAN",
    "puwayan": "POWAYAN",
    "puranpur": "PURANPUR",
    "bagpat": "BAGPAT",
    "baghpat": "BAGPAT",
    "gajraulla": "GAJRAULLA",
    "gajraula": "GAJRAULLA",
    "kaimganj": "KAIAMGANJ",
    "kaiamganj": "KAIAMGANJ",
    "sathiaon": "SATHIAON",
    "budaun": "BUDAUN",
    "bilaspur": "BILASPUR"
}

def extract_mill_from_text(text):
    text_lower = text.lower()
    for kw, mill in mill_map.items():
        if kw in text_lower:
            return mill
    if "corporation" in text_lower or "upssc" in text_lower:
        return "CORPORATION"
    if "federation" in text_lower or "fedration" in text_lower:
        return "FEDRATION"
    return None

pdf_files = []
for root, dirs, files in os.walk(r"D:\gem tenders"):
    for f in files:
        if f.lower().endswith(".pdf"):
            pdf_files.append(os.path.join(root, f))

results = []
for pf in pdf_files:
    try:
        reader = pypdf.PdfReader(pf)
        text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t: text += t
        
        # Extract Bid Number
        # Bid Number pattern: GEM/2026/B/7712863 or similar
        bid_match = re.search(r"GEM/\d{4}/B/\d+", text)
        if not bid_match:
            bid_match = re.search(r"GEM\s*-\s*Bidding\s*-\s*(\d+)", os.path.basename(pf), re.I)
            if bid_match:
                bid_no = f"GEM/2026/B/{bid_match.group(1)}"
            else:
                # try finding any 7-digit number in filename
                num_match = re.search(r"(\d{7})", os.path.basename(pf))
                if num_match:
                    bid_no = f"GEM/2026/B/{num_match.group(1)}"
                else:
                    bid_no = None
        else:
            bid_no = bid_match.group(0)
            
        mill = extract_mill_from_text(text)
        
        results.append({
            "file": os.path.basename(pf),
            "bid_no": bid_no,
            "mill": mill,
            "has_text": len(text.strip()) > 0
        })
    except Exception as e:
        results.append({
            "file": os.path.basename(pf),
            "error": str(e)
        })

print(f"Total processed: {len(results)}")
print("\nFirst 30 mapping results:")
for r in results[:30]:
    print(r)

with open(r"d:\tenderTracker\temp_dir\pdf_mappings.json", "w") as f:
    json.dump(results, f, indent=4)
