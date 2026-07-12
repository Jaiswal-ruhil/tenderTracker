import sqlite3
import json

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

print(f"Total bids: {len(rows)}")

# Let's clean the mill names to standard/common variations as well
cleaned_mills = {
    "NAJIBABAD": ["najibabad"],
    "ANOOPSHAHR": ["anoopshahr", "anupshahar", "anupshahr"],
    "SULTANPUR": ["sultanpur"],
    "NANPARA": ["nanpara"],
    "BELRAYAN": ["belrayan"],
    "SAMPURNANAGAR": ["sampurnanagar", "sampurna nagar"],
    "RAMALA": ["ramala", "ramala"],
    "MORNA": ["morna"],
    "GHOSI": ["ghosi"],
    "NANAUTA": ["nanauta"],
    "SEMIKHERA": ["semikhera"],
    "SARSAWAN": ["sarsawan"],
    "MAHMUDABAD": ["mahmudabad", "mahmoodabad"],
    "TILHAR": ["tilhar"],
    "BISALPUR": ["bisalpur"],
    "POWAYAN": ["powayan", "puwayan"],
    "PURANPUR": ["puranpur"],
    "BAGPAT": ["bagpat", "baghpat"],
    "GAJRAULLA": ["gajraulla", "gajraula"],
    "FEDRATION": ["fedration", "federation"],
    "CORPORATION": ["corporation"],
    "KAIAMGANJ": ["kaiamganj", "kaimganj"],
    "SATHIAON": ["sathiaon"],
    "BUDAUN": ["budaun"],
    "BILASPUR": ["bilaspur"]
}

match_counts = {m: 0 for m in cleaned_mills}

for row in rows:
    row_dict = dict(row)
    # Concatenate all values into a single text block
    text = " ".join([str(val) for val in row_dict.values() if val]).lower()
    for mill, variants in cleaned_mills.items():
        for variant in variants:
            if variant in text:
                match_counts[mill] += 1
                break

print("\nSubstring match counts:")
for mill, count in match_counts.items():
    print(f"{mill}: {count}")

conn.close()
