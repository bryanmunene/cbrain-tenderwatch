"""
Web Push Notifications for Mobile Devices
Requires: pip install pywebpush
"""
from typing import List, Dict
import json

class PushNotificationService:
    """
    Service for sending web push notifications to mobile/desktop browsers
    Uses Web Push API standard (works on Android Chrome, iOS Safari 16.4+)
    """
    
    def __init__(self):
        self.subscriptions: List[Dict] = []  # Store in database in production
        self.vapid_private_key = None  # Generate with: webpush generate_vapid_keys
        self.vapid_public_key = None
        self.vapid_claims = {
            "sub": "mailto:admin@cbrain.net"  # Your contact email
        }
    
    def send_notification(self, subscription_info: Dict, notification_data: Dict):
        """
        Send push notification to a subscribed device
        
        Args:
            subscription_info: Browser subscription object (endpoint, keys)
            notification_data: {title, body, icon, url, badge}
        """
        try:
            from pywebpush import webpush
            
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(notification_data),
                vapid_private_key=self.vapid_private_key,
                vapid_claims=self.vapid_claims
            )
            return True
        except ImportError:
            print("⚠️ pywebpush not installed. Run: pip install pywebpush")
            return False
        except Exception as e:
            print(f"❌ Push notification failed: {e}")
            return False
    
    def notify_new_tenders(self, tenders: list):
        """Send notifications for new high-score tenders"""
        if not tenders:
            return
        
        high_score_tenders = [t for t in tenders if t.score >= 70]
        
        if not high_score_tenders:
            return
        
        notification = {
            "title": f"🎯 {len(high_score_tenders)} New High-Score Tenders!",
            "body": f"Top: {high_score_tenders[0].title[:50]}...",
            "icon": "/static/icon-192x192.png",
            "badge": "/static/badge-72x72.png",
            "url": "/",
            "tag": "new-tenders",
            "requireInteraction": True  # Keep notification visible
        }
        
        # Send to all subscribed devices
        for subscription in self.subscriptions:
            self.send_notification(subscription, notification)


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
