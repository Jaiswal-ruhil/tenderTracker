import sqlite3
import os

db_path = r"D:\gem tenders\database\tenders_db.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute("SELECT bid_no, pdf_path FROM bids WHERE pdf_path IS NOT NULL AND pdf_path != '' AND pdf_path != '[]'")
rows = cursor.fetchall()

print(f"Bids with pdf_path: {len(rows)}")
for r in rows[:10]:
    print(f"Bid: {r['bid_no']}, pdf_path: {r['pdf_path']}")
    # Check if the file exists
    # pdf_path might be a JSON list or a string
    try:
        import json
        paths = json.loads(r['pdf_path'])
        if isinstance(paths, list):
            for p in paths:
                print(f"  File: {p}, Exists: {os.path.exists(p)}")
        else:
            print(f"  File: {paths}, Exists: {os.path.exists(paths)}")
    except Exception as e:
        print(f"  Error parsing path: {e}")

conn.close()
