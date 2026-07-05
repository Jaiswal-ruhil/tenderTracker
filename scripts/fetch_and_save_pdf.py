import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'core'))

from core import db
from core import scraper
import logger

BID = "GEM/2026/B/7703155"
DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', 'temp_dir', 'downloads')

if __name__ == '__main__':
    try:
        # Ensure DB initialized
        db.init_db_path()

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        logger.log('info', f'Fetching PDF for {BID} to {DOWNLOAD_DIR}')
        pdf_path = scraper.download_tender_pdf(BID, DOWNLOAD_DIR, log_fn=logger.log, headless=True)
        if not pdf_path:
            logger.log('err', f'Failed to download PDF for {BID}')
            sys.exit(2)

        # Upsert tender with pdf_path and mark as fetched
        record = {'bid_no': BID, 'bid_url': f'https://bidplus.gem.gov.in/showbidDocument/{BID.split("/")[-1]}', 'pdf_path': os.path.abspath(pdf_path), 'is_fetched': True}
        db.upsert_tender(record)
        logger.log('ok', f'Saved PDF path for {BID} into DB: {record["pdf_path"]}')
        sys.exit(0)
    except Exception as e:
        logger.log('err', f'Error during fetch: {e}')
        raise
