"""
Web Push Notifications for mobile and desktop browsers.
"""

import json
import logging
import os
from typing import Dict


class PushNotificationService:
    """
    Service for sending Web Push notifications to subscribed browsers.
    """

    def __init__(self, app=None):
        self.app = app
        self.vapid_private_key = self._load_vapid_private_key()
        self.vapid_public_key = self._load_vapid_public_key()
        self.vapid_claims = {
            "sub": os.getenv("VAPID_SUBJECT", "mailto:admin@cbrain.net")
        }

    def _load_vapid_private_key(self):
        """Load the VAPID private key from env or disk."""
        env_key = os.getenv("VAPID_PRIVATE_KEY")
        if env_key:
            return env_key

        key_path = os.getenv("VAPID_PRIVATE_KEY_PATH", "vapid_private.pem")
        try:
            with open(key_path, "r", encoding="utf-8") as handle:
                return handle.read()
        except FileNotFoundError:
            return None

    def _load_vapid_public_key(self):
        """Load the VAPID public key from env or disk."""
        env_key = os.getenv("VAPID_PUBLIC_KEY")
        if env_key:
            return env_key

        key_path = os.getenv("VAPID_PUBLIC_KEY_PATH", "vapid_public.pem")
        try:
            with open(key_path, "r", encoding="utf-8") as handle:
                return handle.read()
        except FileNotFoundError:
            return None

    def get_subscriptions(self):
        """Return active push subscriptions from the database."""
        if not self.app:
            return []

        with self.app.app_context():
            from app.models import PushSubscription

            subscriptions = PushSubscription.query.filter_by(active=True).all()
            return [
                {
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh_key,
                        "auth": sub.auth_key,
                    },
                }
                for sub in subscriptions
            ]

    def send_notification(self, subscription_info: Dict, notification_data: Dict):
        """Send a push notification to a subscribed browser."""
        if not self.vapid_private_key:
            logging.warning("VAPID private key is not configured; skipping push notification")
            return False

        try:
            from pywebpush import webpush

            result = webpush(
                subscription_info=subscription_info,
                data=json.dumps(notification_data),
                vapid_private_key=self.vapid_private_key,
                vapid_claims=self.vapid_claims,
            )
            logging.info("Push notification sent: %s", result.status_code)
            return True
        except ImportError:
            logging.error("pywebpush not installed. Run: pip install pywebpush")
            return False
        except Exception as exc:
            logging.error("Push notification failed: %s", exc)
            if hasattr(exc, "response") and getattr(exc.response, "status_code", None) == 410:
                self._deactivate_subscription(subscription_info["endpoint"])
            return False

    def _deactivate_subscription(self, endpoint):
        """Mark a subscription as inactive after a 410 Gone response."""
        if not self.app:
            return

        with self.app.app_context():
            from app.extensions import db
            from app.models import PushSubscription

            subscription = PushSubscription.query.filter_by(endpoint=endpoint).first()
            if subscription:
                subscription.active = False
                db.session.commit()
                logging.info("Deactivated expired subscription")

    @staticmethod
    def _tender_value(tender, field: str, default=None):
        if isinstance(tender, dict):
            return tender.get(field, default)
        try:
            value = getattr(tender, field)
        except Exception:
            return default
        return default if value is None else value

    def notify_new_tenders(self, tenders: list):
        """Send notifications for new high-score tenders."""
        if not tenders:
            return

        if self.app:
            with self.app.app_context():
                from app.models import AppSettings

                settings = AppSettings.query.first()
                if not settings or not settings.notifications_enabled:
                    return
                min_score = float(settings.min_score_to_notify or 50.0)
        else:
            min_score = 50.0

        high_score_tenders = [
            tender
            for tender in tenders
            if float(self._tender_value(tender, "score", 0) or 0) >= min_score
        ]
        if not high_score_tenders:
            return

        lead_tender = high_score_tenders[0]
        lead_title = str(self._tender_value(lead_tender, "title", "Untitled tender"))
        lead_id = self._tender_value(lead_tender, "id", "")

        notification = {
            "title": f"{len(high_score_tenders)} New High-Score Tenders",
            "body": f"Top: {lead_title[:80]}",
            "icon": "/static/icon-192.png",
            "badge": "/static/icon-72.png",
            "data": {
                "url": f"/tender/{lead_id}",
                "tender_id": lead_id,
            },
            "tag": f"tender-{lead_id}",
            "requireInteraction": True,
        }

        subscriptions = self.get_subscriptions()
        success_count = 0
        for subscription in subscriptions:
            if self.send_notification(subscription, notification):
                success_count += 1

        logging.info("Sent notifications to %s/%s devices", success_count, len(subscriptions))


SETUP_INSTRUCTIONS = """
# Mobile Push Notifications Setup

## 1. Generate VAPID Keys
```bash
pip install pywebpush
python -c "from pywebpush import webpush; print(webpush.generate_vapid_keys())"
```

## 2. Add to your .env file
```
VAPID_PUBLIC_KEY=your_public_key_here
VAPID_PRIVATE_KEY=your_private_key_here
VAPID_SUBJECT=mailto:your-email@example.com
```

## 3. Add a subscription UI
Create a browser-side flow that requests notification permission and stores
subscriptions in the PushSubscription table.
"""
