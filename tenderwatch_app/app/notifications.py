"""
Notification system for TenderWatch
Supports desktop notifications and email alerts
"""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.models import AppSettings

logger = logging.getLogger(__name__)


def send_desktop_notification(title, message):
    """Send a desktop notification using plyer"""
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name='TenderWatch',
            timeout=10
        )
        logger.info(f"Desktop notification sent: {title}")
        return True
    except Exception as e:
        logger.error(f"Failed to send desktop notification: {e}")
        return False


def send_email_notification(settings, tenders):
    """Send an email notification about new tenders"""
    if not settings.email_recipients or not settings.smtp_username:
        logger.warning("Email settings not configured")
        return False

    smtp_password = os.getenv("SMTP_PASSWORD") or settings.smtp_password
    if not smtp_password:
        logger.warning("SMTP password is not configured")
        return False

    try:
        recipients = [r.strip() for r in settings.email_recipients.split(",") if r.strip()]
        if not recipients:
            logger.warning("No email recipients configured")
            return False

        subject = f"TenderWatch: {len(tenders)} New Tender{'s' if len(tenders) > 1 else ''} Found"

        html_body = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; }
                .tender { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }
                .high-score { background-color: #d4edda; }
                .medium-score { background-color: #fff3cd; }
                .score { font-weight: bold; color: #0066cc; }
                .title { font-size: 16px; font-weight: bold; color: #333; }
                .category { color: #666; font-style: italic; }
                .deadline { color: #d9534f; font-weight: bold; }
            </style>
        </head>
        <body>
        """
        html_body += f"<h2>TenderWatch Alert</h2><p>Found {len(tenders)} new tender opportunity{'ies' if len(tenders) > 1 else 'y'} matching your criteria:</p>"

        for tender in tenders:
            score_class = "high-score" if tender.score >= 70 else "medium-score" if tender.score >= 50 else ""
            html_body += f"""
            <div class="tender {score_class}">
                <div class="title">{tender.title_translated or tender.title}</div>
                <div class="score">Score: {tender.score:.1f}</div>
                {f'<div class="category">Category: {tender.category}</div>' if tender.category else ''}
                {f'<div>Buyer: {tender.buyer}</div>' if tender.buyer else ''}
                {f'<div>Country: {tender.country}</div>' if tender.country else ''}
                {f'<div class="deadline">Deadline: {tender.deadline}</div>' if tender.deadline else ''}
                <div><a href="{tender.link}">View Tender</a></div>
            </div>
            """

        html_body += "</body></html>"

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = settings.smtp_username
        msg['To'] = ", ".join(recipients)

        text_body = f"TenderWatch Alert\n\nFound {len(tenders)} new tender(s):\n\n"
        for tender in tenders:
            text_body += f"- {tender.title_translated or tender.title} (Score: {tender.score:.1f})\n  {tender.link}\n\n"

        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP(settings.smtp_server, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_username, smtp_password)
            server.send_message(msg)

        logger.info(f"Email notification sent to {len(recipients)} recipient(s)")
        return True

    except Exception as e:
        logger.error(f"Failed to send email notification: {e}")
        return False


def notify_new_tenders(tenders):
    """Send notifications about new tenders based on settings"""
    if not tenders:
        return

    try:
        settings = AppSettings.query.first()
        if not settings or not settings.notifications_enabled:
            return

        notify_tenders = [t for t in tenders if t.score >= settings.min_score_to_notify]
        if not notify_tenders:
            return

        if settings.notify_desktop:
            title = f"TenderWatch: {len(notify_tenders)} New Tender{'s' if len(notify_tenders) > 1 else ''}"
            message = f"Found {len(notify_tenders)} new tender(s) with score >= {settings.min_score_to_notify:.0f}"
            send_desktop_notification(title, message)

        # Email notifications were removed from the app.

    except Exception as e:
        logger.error(f"Error in notify_new_tenders: {e}")
