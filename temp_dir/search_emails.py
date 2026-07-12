import sqlite3
import re

db_path = r"D:\gem tenders\database\tenders_db.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute("SELECT * FROM bids")
rows = cursor.fetchall()

print(f"Total bids: {len(rows)}")

email_matches = {}
for r in rows:
    r_dict = dict(r)
    text = " | ".join(str(v) for v in r_dict.values() if v).lower()
    emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
    if emails:
        for email in emails:
            email_matches[email] = email_matches.get(email, []) + [r['bid_no']]

print("\nEmail matches:")
for email, bids in email_matches.items():
    print(f"  {email}: {len(bids)} bids")

conn.close()
