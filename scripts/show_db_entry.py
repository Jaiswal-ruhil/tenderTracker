import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'core'))
from core import db

db.init_db_path()
conn = db.get_conn()
cur = conn.cursor()
cur.execute('SELECT bid_no, bid_url, pdf_path, is_fetched FROM tenders WHERE bid_no=?', ('GEM/2026/B/7703155',))
row = cur.fetchone()
print(row)
conn.close()
