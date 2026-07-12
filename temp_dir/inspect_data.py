import sqlite3
import re

db_path = r"D:\gem tenders\database\tenders_db.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute("SELECT * FROM bids")
rows = cursor.fetchall()

mills = [
    "NAJIBABAD", "ANOOPSHAHR", "SULTANPUR", "NANPARA", "BELRAYAN",
    "SAMPURNANAGAR", "RAMALA", "MORNA", "GHOSI", "NANAUTA",
    "SEMIKHERA", "SARSAWAN", "MAHMUDABAD", "TILHAR", "BISALPUR",
    "POWAYAN", "PURANPUR", "BAGPAT", "GAJRAULLA", "FEDRATION",
    "CORPORATION", "KAIAMGANJ", "SATHIAON", "BUDAUN", "BILASPUR"
]

def get_mill_from_bid(r_row):
    r = dict(r_row)
    # Fields to check: location, office, organisation, dept, items, remarks, tags
    fields = [r.get("location"), r.get("office"), r.get("organisation"), r.get("dept"), r.get("items"), r.get("remarks")]
    text = " | ".join(str(f) for f in fields if f).lower()
    
    # Check for specific patterns
    if "najibabad" in text: return "NAJIBABAD"
    if "anoopshahr" in text or "anupshahar" in text or "anupshahr" in text: return "ANOOPSHAHR"
    if "sultanpur" in text: return "SULTANPUR"
    if "nanpara" in text: return "NANPARA"
    if "belrayan" in text: return "BELRAYAN"
    if "sampurnanagar" in text or "sampurna nagar" in text: return "SAMPURNANAGAR"
    if "ramala" in text or "ramla" in text: return "RAMALA"
    if "morna" in text: return "MORNA"
    if "ghosi" in text: return "GHOSI"
    if "nanauta" in text: return "NANAUTA"
    if "semikhera" in text or "semi khera" in text: return "SEMIKHERA"
    if "sarsawan" in text: return "SARSAWAN"
    if "mahmudabad" in text or "mahmoodabad" in text: return "MAHMUDABAD"
    if "tilhar" in text: return "TILHAR"
    if "bisalpur" in text: return "BISALPUR"
    if "powayan" in text or "puwayan" in text: return "POWAYAN"
    if "puranpur" in text: return "PURANPUR"
    if "bagpat" in text or "baghpat" in text: return "BAGPAT"
    if "gajraulla" in text or "gajraula" in text: return "GAJRAULLA"
    if "kaimganj" in text or "kaiamganj" in text: return "KAIAMGANJ"
    if "sathiaon" in text: return "SATHIAON"
    if "budaun" in text: return "BUDAUN"
    if "bilaspur" in text: return "BILASPUR"
    
    if "corporation" in text or "upssc" in text:
        return "CORPORATION"
        
    if "federation" in text or "fedration" in text:
        return "FEDRATION"
        
    return None

mapped_bids = {}
for r in rows:
    mill = get_mill_from_bid(r)
    mapped_bids[mill] = mapped_bids.get(mill, 0) + 1

print("Mapping results:")
for m in sorted(mills):
    print(f"  {m}: {mapped_bids.get(m, 0)}")
print(f"  None (Unmapped): {mapped_bids.get(None, 0)}")

# Let's look at the bids that map to SATHIAON or TILHAR or NAJIBABAD, etc.
print("\nChecking some mapped bids:")
found = 0
for r in rows:
    mill = get_mill_from_bid(r)
    if mill != "FEDRATION" and mill is not None:
        loc = r['location'] if r['location'] else ''
        loc = loc.encode('ascii', 'replace').decode()
        dept = r['dept'] if r['dept'] else ''
        dept = dept.encode('ascii', 'replace').decode()
        items = r['items'] if r['items'] else ''
        items = items.encode('ascii', 'replace').decode()
        print(f"Bid: {r['bid_no']}, Mill: {mill}, Location: {loc}, Dept: {dept}, Items: {items[:50]}")
        found += 1
        if found >= 15:
            break

conn.close()
