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

# We need to map spelling variations
mill_regexes = {
    "NAJIBABAD": re.compile(r"najibabad", re.I),
    "ANOOPSHAHR": re.compile(r"anoopshahr|anupshahar|anupshahr", re.I),
    "SULTANPUR": re.compile(r"sultanpur", re.I),
    "NANPARA": re.compile(r"nanpara", re.I),
    "BELRAYAN": re.compile(r"belrayan", re.I),
    "SAMPURNANAGAR": re.compile(r"sampurnanagar|sampurna\s+nagar", re.I),
    "RAMALA": re.compile(r"ramala|ramla", re.I),
    "MORNA": re.compile(r"morna", re.I),
    "GHOSI": re.compile(r"ghosi", re.I),
    "NANAUTA": re.compile(r"nanauta", re.I),
    "SEMIKHERA": re.compile(r"semikhera|semi\s+khera", re.I),
    "SARSAWAN": re.compile(r"sarsawan", re.I),
    "MAHMUDABAD": re.compile(r"mahmudabad|mahmoodabad", re.I),
    "TILHAR": re.compile(r"tilhar", re.I),
    "BISALPUR": re.compile(r"bisalpur", re.I),
    "POWAYAN": re.compile(r"powayan|puwayan", re.I),
    "PURANPUR": re.compile(r"puranpur", re.I),
    "BAGPAT": re.compile(r"bagpat|baghpat", re.I),
    "GAJRAULLA": re.compile(r"gajraulla|gajraula", re.I),
    "FEDRATION": re.compile(r"fedration|federation", re.I),
    "CORPORATION": re.compile(r"corporation", re.I),
    "KAIAMGANJ": re.compile(r"kaiamganj|kaimganj", re.I),
    "SATHIAON": re.compile(r"sathiaon|sathiaon", re.I),
    "BUDAUN": re.compile(r"budaun", re.I),
    "BILASPUR": re.compile(r"bilaspur", re.I),
}

mapped_counts = {m: 0 for m in mills}
unmapped = 0

for r in rows:
    r_dict = dict(r)
    # Fields to check: location, organisation, office, dept, items, remarks, tags
    search_str = " | ".join(str(r_dict[col]) for col in ["location", "organisation", "office", "dept", "items", "remarks"] if r_dict[col])
    
    matched = False
    for mill, regex in mill_regexes.items():
        if regex.search(search_str):
            mapped_counts[mill] += 1
            matched = True
            
    if not matched:
        unmapped += 1
        if unmapped <= 5:
            print(f"Unmapped Bid {r_dict['bid_no']}: {search_str}")

print("\nMapped Counts:")
for mill, count in mapped_counts.items():
    print(f"{mill}: {count}")
print(f"Unmapped: {unmapped}")

conn.close()
