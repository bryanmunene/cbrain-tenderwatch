"""
Background scheduler for autonomous tender scanning.
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
scheduler_started = False


def scheduled_scan(app):
    """Run a scan in the app context."""
    with app.app_context():
        try:
            from app.extensions import db
            from app.notifications import notify_new_tenders
            from app.scraper import run_scan
            from app.models import TenderResult

            logger.info("Starting scheduled scan...")

            new_tenders = run_scan()

            for tender in new_tenders:
                tender.notified = False
            db.session.commit()

            unnotified = TenderResult.query.filter_by(notified=False).all()
            if unnotified:
                logger.info("Found %s new tenders to notify", len(unnotified))
                notify_new_tenders(unnotified)
                for tender in unnotified:
                    tender.notified = True
                db.session.commit()

            logger.info("Scheduled scan complete. Found %s new tenders.", len(new_tenders))
        except Exception as exc:
            logger.error("Error in scheduled scan: %s", exc)


def start_scheduler(app):
    """Start the background scheduler with settings from database."""
    global scheduler_started

    if not app.config.get("ENABLE_INTERNAL_SCHEDULER"):
        logger.info("Internal scheduler is disabled for this process")
        return

    if scheduler_started:
        return

    with app.app_context():
        from app.extensions import db
        from app.models import AppSettings

        try:
            settings = AppSettings.query.first()
            if not settings:
                settings = AppSettings()
                db.session.add(settings)
                db.session.commit()
        except Exception as exc:
            logger.warning("Scheduler initialization skipped: %s", exc)
            return

        if settings.auto_scan_enabled:
            scheduler.add_job(
                func=lambda: scheduled_scan(app),
                trigger=IntervalTrigger(minutes=settings.scan_interval_minutes),
                id="tender_scan_job",
                name="Scan for new tenders",
                replace_existing=True,
            )
            scheduler.start()
            scheduler_started = True
            logger.info("Scheduler started: scanning every %s minutes", settings.scan_interval_minutes)
        else:
            logger.info("Auto-scan is disabled")


def stop_scheduler():
    """Stop the background scheduler."""
    global scheduler_started

    if scheduler_started and scheduler.running:
        scheduler.shutdown(wait=False)
        scheduler_started = False
        logger.info("Scheduler stopped")


def restart_scheduler(app):
    """Restart the scheduler with updated settings."""
    stop_scheduler()
    start_scheduler(app)


def get_scheduler_status():
    """Get the current status of the scheduler."""
    return {
        "running": scheduler_started and scheduler.running,
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            }
            for job in scheduler.get_jobs()
        ]
        if scheduler_started
        else [],
    }
