import os, shutil, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'core'))
from core import db
import logger

BID = 'GEM/2026/B/7703155'
ORIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'temp_dir', 'downloads', f'GeM-Bidding-GEM_2026_B_7703155.pdf'))

if __name__ == '__main__':
    try:
        db.init_db_path()
        resolved = db.get_resolved_db_path()
        dest_dir = os.path.dirname(resolved) or os.getcwd()
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, os.path.basename(ORIG_PATH))
        if not os.path.exists(ORIG_PATH):
            logger.log('err', f'Original PDF not found: {ORIG_PATH}')
            sys.exit(1)
        # Copy file
        shutil.copy2(ORIG_PATH, dest_path)
        logger.log('ok', f'Copied PDF to DB folder: {dest_path}')
        # Update DB
        record = {'bid_no': BID, 'pdf_path': os.path.abspath(dest_path), 'is_fetched': True}
        db.upsert_tender(record)
        logger.log('ok', f'Updated DB pdf_path for {BID}')
    except Exception as e:
        logger.log('err', f'Failed to move and update PDF: {e}')
        raise
