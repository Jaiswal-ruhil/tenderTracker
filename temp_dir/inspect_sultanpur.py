import sqlite3

db_path = r"D:\gem tenders\database\tenders_db.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

ids = ["7708891", "7641694", "7717878", "7703715"]
for i in ids:
    cursor.execute("SELECT * FROM bids WHERE bid_no LIKE ?", (f"%{i}%",))
    rows = cursor.fetchall()
    print(f"\nID {i}: {len(rows)} matches")
    for r in rows:
        d = dict(r)
        for k, v in d.items():
            if v:
                print(f"  {k}: {repr(v)}")

conn.close()
