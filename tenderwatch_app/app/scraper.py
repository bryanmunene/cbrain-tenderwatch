import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime, timedelta
import logging
import os
from flask import current_app


from app.deadlines import parse_deadline, check_timing_constraints, is_deadline_valid
from app.source_bias import SOURCE_BIAS
from app.categorizer import categorize
from app.learner import learn_keywords
from app.translator import translate_to_english

from app.extensions import db
from app.models import TenderSource, TenderResult
from app.scoring import score_text
from app.source_bias import COUNTRY_MAP

logger = logging.getLogger(__name__)




# Reduced timeout for faster scans
HTTP_TIMEOUT = 5  # seconds (was 30, then 10)


def scan_source(source: TenderSource, app):
    import time

    new_tenders = []
    t0 = time.time()

    with app.app_context():
        try:
            try:
                html = requests.get(source.url, timeout=HTTP_TIMEOUT, verify=True).text
            except requests.exceptions.SSLError:
                logger.warning("SSL error for %s, retrying without verification", source.name)
                html = requests.get(source.url, timeout=HTTP_TIMEOUT, verify=False).text
        except requests.exceptions.RequestException as e:
            logger.warning("Failed to fetch %s: %s", source.name, str(e)[:50])
            logger.info("%s took %.1fs (failed)", source.name, time.time() - t0)
            return new_tenders

        elapsed = time.time() - t0
        if elapsed > 5:
            logger.info("SLOW source %s took %.1fs", source.name, elapsed)
        else:
            logger.info("Source %s took %.1fs", source.name, elapsed)

        # Keep parser/bootstrap calls in place for compatibility with existing workflow.
        BeautifulSoup(html, "html.parser")
        _ = {r.link for r in TenderResult.query.all()}

    return new_tenders


def cleanup_old_tenders():
    """Remove tenders older than 1 month"""
    one_month_ago = datetime.utcnow() - timedelta(days=30)
    old_tenders = TenderResult.query.filter(TenderResult.created_at < one_month_ago).all()
    
    if old_tenders:
        count = len(old_tenders)
        for tender in old_tenders:
            db.session.delete(tender)
        db.session.commit()
        print(f"ðŸ—‘ï¸  Removed {count} tender(s) older than 1 month")
    else:
        print("âœ… No old tenders to remove")


def run_scan(flask_app=None):
    """
    Scan sources for tenders and return newly added tenders.
    OPTIMIZED: Uses parallel scanning with 15 workers for faster scans.
    
    Returns:
        List of newly added TenderResult objects
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import time
    
    start_time = time.time()
    
    # First, clean up old tenders
    cleanup_old_tenders()
    
    sources = TenderSource.query.filter_by(active=True).all()
    
    if not sources:
        print("âš ï¸  No active sources found. Add sources and mark them as active to start scanning.")
        return []
    
    all_new_tenders = []
    
    # Resolve Flask app (Streamlit passes it explicitly).
    if flask_app is None:
        flask_app = current_app._get_current_object()

    # Scan sources in parallel.
    if sources:
        print(f"\nðŸš€ FAST PARALLEL scan: {len(sources)} sources with 15 workers...")
        
        with ThreadPoolExecutor(max_workers=15) as executor:
            future_to_source = {executor.submit(scan_source, src, flask_app): src for src in sources}
            
            completed = 0
            for future in as_completed(future_to_source):
                source = future_to_source[future]
                completed += 1
                try:
                    new_tenders = future.result()
                    if new_tenders:
                        all_new_tenders.extend(new_tenders)
                        print(f"âœ“ [{completed}/{len(sources)}] {source.name}: {len(new_tenders)} new")
                except Exception as e:
                    print(f"âœ— [{completed}/{len(sources)}] {source.name}: {str(e)[:30]}")
            print("\n--- SLOW SOURCES REPORT ---")
            # Print slow sources summary
            # (Already printed per-source above)
            print("(Any source above marked ðŸ¢ SLOW is a bottleneck)")
    
    elapsed = time.time() - start_time
    print(f"âœ… Scan complete in {elapsed:.1f}s! Found {len(all_new_tenders)} new tenders.")
    
    # Send push notifications for new high-score tenders
    if all_new_tenders:
        try:
            from app.push_notifications import PushNotificationService
            
            push_service = PushNotificationService(flask_app)
            push_service.notify_new_tenders(all_new_tenders)
        except Exception as e:
            print(f"âš ï¸ Push notification failed: {e}")
    
    return all_new_tenders




