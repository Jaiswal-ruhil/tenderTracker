import sqlite3

db_path = r"D:\gem tenders\database\tenders_db.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT * FROM bids")
rows = cursor.fetchall()

print(f"Total bids: {len(rows)}")
found = 0
for r in rows:
    d = dict(r)
    s = " | ".join(str(v) for v in d.values() if v)
    if "najibabad" in s.lower():
        found += 1
        print(f"Match {found}: Bid {d['bid_no']}")
        print(d)

if found == 0:
    print("No bids containing 'najibabad' found at all!")

conn.close()
