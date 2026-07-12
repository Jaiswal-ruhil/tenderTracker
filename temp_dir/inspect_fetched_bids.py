import sqlite3

db_path = r"D:\gem tenders\database\tenders_db.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT bid_no, location, dept, items, filing_status, matched_firm FROM bids WHERE location IS NOT NULL AND location != ''")
rows = cursor.fetchall()

print(f"Total fetched bids: {len(rows)}")
for idx, r in enumerate(rows):
    loc = r['location']
    if loc:
        loc = loc.encode('ascii', 'replace').decode()
    dept = r['dept']
    if dept:
        dept = dept.encode('ascii', 'replace').decode()
    items = r['items']
    if items:
        items = items.encode('ascii', 'replace').decode()
        
    print(f"\n{idx+1}. Bid: {r['bid_no']}")
    print(f"   Location: {loc}")
    print(f"   Dept:     {dept}")
    print(f"   Items:    {items}")
    print(f"   Filing:   {r['filing_status']}")
    print(f"   Firm:     {r['matched_firm']}")

conn.close()
