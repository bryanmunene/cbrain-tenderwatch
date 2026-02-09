"""
Web Push Notifications for Mobile Devices
Requires: pip install pywebpush
"""
from typing import List, Dict
import json
import os
import logging

class PushNotificationService:
    """
    Service for sending web push notifications to mobile/desktop browsers
    Uses Web Push API standard (works on Android Chrome, iOS Safari 16.4+)
    """
    
    def __init__(self, app=None):
        self.app = app
        
        # Load VAPID keys from files or environment
        self.vapid_private_key = self._load_vapid_private_key()
        self.vapid_public_key = self._load_vapid_public_key()
        
        self.vapid_claims = {
            "sub": os.getenv("VAPID_SUBJECT", "mailto:admin@cbrain.net")
        }
    
    def _load_vapid_private_key(self):
        """Load VAPID private key from file or environment"""
        env_key = os.getenv("VAPID_PRIVATE_KEY")
        if env_key:
            return env_key

        key_path = os.getenv("VAPID_PRIVATE_KEY_PATH", "vapid_private.pem")
        try:
            with open(key_path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            return None
    
    def _load_vapid_public_key(self):
        """Load VAPID public key from file or environment"""
        env_key = os.getenv("VAPID_PUBLIC_KEY")
        if env_key:
            return env_key

        key_path = os.getenv("VAPID_PUBLIC_KEY_PATH", "vapid_public.pem")
        try:
            with open(key_path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            return None
    
    def get_subscriptions(self):
        """Get all active push subscriptions from database"""
        if self.app:
            with self.app.app_context():
                from app.models import PushSubscription
                subs = PushSubscription.query.filter_by(active=True).all()
                return [{
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh_key,
                        "auth": sub.auth_key
                    }
                } for sub in subs]
        return []
    
    def send_notification(self, subscription_info: Dict, notification_data: Dict):
        """
        Send push notification to a subscribed device
        
        Args:
            subscription_info: Browser subscription object (endpoint, keys)
            notification_data: {title, body, icon, url, badge}
        """
        try:
            from pywebpush import webpush
            
            result = webpush(
                subscription_info=subscription_info,
                data=json.dumps(notification_data),
                vapid_private_key=self.vapid_private_key,
                vapid_claims=self.vapid_claims
            )
            logging.info(f"✅ Push notification sent: {result.status_code}")
            return True
        except ImportError:
            logging.error("⚠️ pywebpush not installed. Run: pip install pywebpush")
            return False
        except Exception as e:
            logging.error(f"❌ Push notification failed: {e}")
            # If endpoint is gone (410), mark subscription as inactive
            if hasattr(e, 'response') and e.response.status_code == 410:
                self._deactivate_subscription(subscription_info['endpoint'])
            return False
    
    def _deactivate_subscription(self, endpoint):
        """Mark a subscription as inactive when it returns 410 Gone"""
        if self.app:
            with self.app.app_context():
                from app.models import PushSubscription
                from app.extensions import db
                sub = PushSubscription.query.filter_by(endpoint=endpoint).first()
                if sub:
                    sub.active = False
                    db.session.commit()
                    logging.info(f"🗑️ Deactivated expired subscription")
    
    def notify_new_tenders(self, tenders: list):
        """Send notifications for new high-score tenders"""
        if not tenders:
            return
        
        # Get notification settings
        if self.app:
            with self.app.app_context():
                from app.models import AppSettings
                settings = AppSettings.query.first()
                if not settings or not settings.notifications_enabled:
                    return
                
                min_score = settings.min_score_to_notify if settings else 50.0
        else:
            min_score = 50.0
        
        high_score_tenders = [t for t in tenders if t.score >= min_score]
        
        if not high_score_tenders:
            return
        
        notification = {
            "title": f"🎯 {len(high_score_tenders)} New High-Score Tenders!",
            "body": f"Top: {high_score_tenders[0].title[:80]}",
            "icon": "/static/icon-192x192.png",
            "badge": "/static/badge-72x72.png",
            "data": {
                "url": f"/tender/{high_score_tenders[0].id}",
                "tender_id": high_score_tenders[0].id
            },
            "tag": f"tender-{high_score_tenders[0].id}",
            "requireInteraction": True
        }
        
        # Send to all subscribed devices
        subscriptions = self.get_subscriptions()
        success_count = 0
        for subscription in subscriptions:
            if self.send_notification(subscription, notification):
                success_count += 1
        
        logging.info(f"📱 Sent notifications to {success_count}/{len(subscriptions)} devices")


# Setup instructions stored as constant
SETUP_INSTRUCTIONS = """
# Mobile Push Notifications Setup

## 1. Generate VAPID Keys (one-time)
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

## 3. Update service-worker.js
Add push notification handler to handle incoming notifications.

## 4. Add subscription UI
Create a "🔔 Enable Notifications" button in settings page.

## 5. Store subscriptions in database
Add PushSubscription model to store user device subscriptions.

## Browser Support:
✅ Android Chrome 42+
✅ Android Firefox 44+
✅ iOS Safari 16.4+ (iOS 16.4 or later)
✅ Desktop Chrome/Firefox/Edge
❌ iOS Safari < 16.4

## Testing:
1. Deploy to HTTPS (required for Web Push API)
2. Click "Enable Notifications" in app
3. Allow notifications when prompted
4. Run a scan - notifications should appear for high-score tenders
"""
