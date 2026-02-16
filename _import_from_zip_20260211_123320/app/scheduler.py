"""
Background scheduler for autonomous tender scanning
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
scheduler_started = False


def scheduled_scan(app):
    """Run a scan in the app context"""
    with app.app_context():
        try:
            from app.scraper import run_scan
            from app.models import TenderResult, AppSettings
            from app.notifications import notify_new_tenders
            from app.extensions import db
            
            logger.info("Starting scheduled scan...")
            
            # Get current tender count
            before_count = TenderResult.query.count()
            
            # Run scan
            new_tenders = run_scan()
            
            # Mark new tenders as not notified yet
            for tender in new_tenders:
                tender.notified = False
            db.session.commit()
            
            # Get tenders that haven't been notified
            unnotified = TenderResult.query.filter_by(notified=False).all()
            
            if unnotified:
                logger.info(f"Found {len(unnotified)} new tenders to notify")
                notify_new_tenders(unnotified)
                
                # Mark as notified
                for tender in unnotified:
                    tender.notified = True
                db.session.commit()
            
            logger.info(f"Scheduled scan complete. Found {len(new_tenders)} new tenders.")
            
        except Exception as e:
            logger.error(f"Error in scheduled scan: {e}")


def start_scheduler(app):
    """Start the background scheduler with settings from database"""
    global scheduler_started
    
    if scheduler_started:
        return
    
    with app.app_context():
        from app.models import AppSettings
        from app.extensions import db
        
        try:
            # Ensure settings exist
            settings = AppSettings.query.first()
            if not settings:
                settings = AppSettings()
                db.session.add(settings)
                db.session.commit()
        except Exception as e:
            # Handle case where database schema is out of sync (e.g., missing columns)
            print(f"⚠️  Scheduler initialization skipped: {e}")
            print("   Run migration script or restart app after database updates")
            return
        
        if settings.auto_scan_enabled:
            # Add scheduled job
            scheduler.add_job(
                func=lambda: scheduled_scan(app),
                trigger=IntervalTrigger(minutes=settings.scan_interval_minutes),
                id='tender_scan_job',
                name='Scan for new tenders',
                replace_existing=True
            )
            
            scheduler.start()
            scheduler_started = True
            logger.info(f"Scheduler started: scanning every {settings.scan_interval_minutes} minutes")
        else:
            logger.info("Auto-scan is disabled")


def stop_scheduler():
    """Stop the background scheduler"""
    global scheduler_started
    
    if scheduler_started and scheduler.running:
        scheduler.shutdown()
        scheduler_started = False
        logger.info("Scheduler stopped")


def restart_scheduler(app):
    """Restart the scheduler with updated settings"""
    stop_scheduler()
    start_scheduler(app)


def get_scheduler_status():
    """Get the current status of the scheduler"""
    global scheduler_started
    
    return {
        'running': scheduler_started and scheduler.running,
        'jobs': [
            {
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None
            }
            for job in scheduler.get_jobs()
        ] if scheduler_started else []
    }
