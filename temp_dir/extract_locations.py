import sqlite3

db_path = r"D:\gem tenders\database\tenders_db.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT DISTINCT location FROM bids WHERE location IS NOT NULL AND location != ''")
locations = [r[0] for r in cursor.fetchall()]
conn.close()

print(f"Total distinct locations: {len(locations)}")
print("Sample locations containing 'mill' or 'chini' or 'sugar' or 'up':")
matched = []
for loc in locations:
    loc_lower = loc.lower()
    if "mill" in loc_lower or "chini" in loc_lower or "sugar" in loc_lower or "corp" in loc_lower:
        matched.append(loc)

for m in sorted(matched)[:50]:
    print("-", m)
