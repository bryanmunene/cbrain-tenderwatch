# 📱 Mobile App & Push Notifications Guide

## Mobile App Installation (Already Built!)

### The Flask version has full PWA support:

**Install on Android:**
1. Open https://your-app-url.com in Chrome
2. Tap menu (⋮) → "Add to Home Screen"
3. App installs with icon on home screen
4. Works offline with cached data

**Install on iOS (Safari 16.4+):**
1. Open the URL in Safari
2. Tap Share button → "Add to Home Screen"
3. Name the app and tap "Add"
4. Launch from home screen like native app

### PWA Features Already Implemented:
- ✅ Offline caching (service-worker.js)
- ✅ App manifest (name, icons, colors)
- ✅ Installable prompt
- ✅ Standalone mode (no browser UI)
- ✅ Fast loading (cached assets)

## Push Notifications Setup

### Quick Start (5 steps):

#### 1. Install Required Package
```bash
cd tenderwatch_app
pip install pywebpush
pip freeze > requirements.txt
```

#### 2. Generate VAPID Keys (one-time only)
```bash
python -c "from pywebpush import webpush; import json; keys = webpush.generate_vapid_keys(); print(json.dumps(keys, indent=2))"
```

Save the output - you'll need both keys.

#### 3. Set Environment Variables
Create `.env` file in `tenderwatch_app/`:
```env
VAPID_PUBLIC_KEY=BEy1a2b3c4d5e6f7...
VAPID_PRIVATE_KEY=abcdefgh123456...
VAPID_SUBJECT=mailto:admin@yourdomain.com
```

#### 4. Update Database Model
Add to `models.py`:
```python
class PushSubscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    endpoint = db.Column(db.String(500), unique=True)
    p256dh = db.Column(db.String(200))
    auth = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

#### 5. Deploy to HTTPS
Push notifications require HTTPS. Free options:
- **Streamlit Cloud**: Automatic HTTPS ✅
- **Railway**: Automatic HTTPS ✅
- **Render**: Automatic HTTPS ✅
- **Heroku**: Free tier with HTTPS

### How It Works:

```
New Tender Detected
       ↓
Score >= 70%?
       ↓
Send Push to All Subscribed Devices
       ↓
Notification appears on user's phone
(even if app is closed!)
```

### User Experience:

1. **First Visit:**
   - User opens app
   - Clicks "🔔 Enable Notifications" in Settings
   - Browser prompts: "Allow notifications?"
   - User clicks "Allow"
   - Device registered for push notifications

2. **When New Tender Found:**
   - Scan runs (manual or auto-scan)
   - High-score tender detected (≥70%)
   - Push notification sent to ALL subscribed devices
   - User sees: "🎯 3 New High-Score Tenders!"
   - Taps notification → App opens to results

### Notification Settings:

Add to `AppSettings` model:
- `push_notifications_enabled` (Boolean)
- `min_score_for_notification` (Integer, default: 70)
- `notification_sound` (Boolean, default: True)

### Browser Support:

| Platform | Browser | Support |
|----------|---------|---------|
| Android | Chrome | ✅ Full |
| Android | Firefox | ✅ Full |
| iOS 16.4+ | Safari | ✅ Full |
| iOS <16.4 | Safari | ❌ No |
| Desktop | Chrome/Edge/Firefox | ✅ Full |

### Implementation Priority:

**Already Working:**
1. ✅ PWA installable on mobile
2. ✅ Desktop notifications (plyer)
3. ✅ Auto-scan scheduling

**Needs Implementation:**
1. ⏳ VAPID key generation (5 min)
2. ⏳ Push subscription storage (10 min)
3. ⏳ Notification UI button (5 min)
4. ⏳ Push sending logic (15 min)

**Total: ~35 minutes to full mobile push notifications**

### Testing Checklist:

- [ ] Generate VAPID keys
- [ ] Add keys to environment variables
- [ ] Deploy to HTTPS domain
- [ ] Install app on mobile device
- [ ] Click "Enable Notifications" in Settings
- [ ] Grant browser permission
- [ ] Run manual scan
- [ ] Verify notification appears on phone
- [ ] Test with app closed
- [ ] Test with phone locked

### Troubleshooting:

**Notifications not appearing?**
1. Check HTTPS (required for Web Push)
2. Verify VAPID keys in environment
3. Check browser console for errors
4. Ensure subscription saved in database
5. Test with https://tests.peter.sh/notification-generator/

**iOS not working?**
- Requires iOS 16.4 or later
- Must be installed as PWA (not just browser)
- Check Settings → Notifications → Allow

### Alternative: Email Notifications

If push notifications are complex, email is simpler:
```python
# Already in notifications.py structure
def send_email_notification(tender):
    # Use SMTP or SendGrid API
    # No HTTPS required
    # Works everywhere
```

Add SMTP settings to AppSettings:
- smtp_server
- smtp_port
- smtp_username
- smtp_password
- email_recipients

## Recommended Approach:

1. **Phase 1 (Immediate):**
   - Use Flask version for mobile PWA
   - Enable desktop notifications (already working)
   - Deploy to HTTPS hosting

2. **Phase 2 (This Week):**
   - Implement web push notifications
   - Add "Enable Notifications" button
   - Test on Android and iOS

3. **Phase 3 (Optional):**
   - Add email notifications as backup
   - Implement SMS notifications (Twilio)
   - Add notification history page

---

**Want me to implement the full push notification system now? It will take about 30-40 minutes.**
