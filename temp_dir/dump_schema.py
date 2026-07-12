import sqlite3

db_path = r"D:\gem tenders\database\tenders_db.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get table schema
cursor.execute("PRAGMA table_info(bids)")
cols = cursor.fetchall()
print("Table bids columns:")
for c in cols:
    print(f"  {c['name']} ({c['type']})")

cursor.execute("SELECT COUNT(*) FROM bids")
total = cursor.fetchone()[0]
print(f"\nTotal rows: {total}")

# Count non-empty values for each column
print("\nNon-empty counts:")
for col in [c['name'] for c in cols]:
    cursor.execute(f"SELECT COUNT(*) FROM bids WHERE {col} IS NOT NULL AND {col} != '' AND {col} != '[]'")
    count = cursor.fetchone()[0]
    print(f"  {col}: {count}")

# Print first 2 rows
cursor.execute("SELECT * FROM bids LIMIT 2")
rows = cursor.fetchall()
for idx, r in enumerate(rows):
    print(f"\nRow {idx+1}:")
    for k, v in dict(r).items():
        if v:
            print(f"  {k}: {repr(v)}")

conn.close()
