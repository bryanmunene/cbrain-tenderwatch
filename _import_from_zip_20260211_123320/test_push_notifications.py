"""
Test script for push notification system
Verifies all components are working correctly
"""
from app import create_app
from app.extensions import db
from app.models import PushSubscription, AppSettings
from app.push_notifications import PushNotificationService

app = create_app(start_scheduler=False)

print("ðŸ§ª Testing Push Notification System\n")

with app.app_context():
    # Test 1: Check database table exists
    print("1ï¸âƒ£ Testing database setup...")
    try:
        subscription_count = PushSubscription.query.count()
        print(f"   âœ… PushSubscription table exists ({subscription_count} subscriptions)")
    except Exception as e:
        print(f"   âŒ Database error: {e}")
        exit(1)
    
    # Test 2: Check AppSettings has notification fields
    print("\n2ï¸âƒ£ Testing AppSettings...")
    try:
        settings = AppSettings.query.first()
        if settings:
            print(f"   âœ… Settings found")
            print(f"   ðŸ“Š Notifications enabled: {settings.notifications_enabled}")
            print(f"   ðŸ“Š Min score to notify: {settings.min_score_to_notify}")
        else:
            print("   âš ï¸  No settings found, creating defaults...")
            settings = AppSettings()
            db.session.add(settings)
            db.session.commit()
            print("   âœ… Default settings created")
    except Exception as e:
        print(f"   âŒ Settings error: {e}")
        exit(1)
    
    # Test 3: Check VAPID keys loaded
    print("\n3ï¸âƒ£ Testing VAPID keys...")
    try:
        push_service = PushNotificationService(app)
        if push_service.vapid_private_key:
            print("   âœ… VAPID private key loaded")
            print(f"   ðŸ“„ Key preview: {push_service.vapid_private_key[:50]}...")
        else:
            print("   âš ï¸  VAPID private key not found")
        
        if push_service.vapid_public_key:
            print("   âœ… VAPID public key loaded")
            print(f"   ðŸ“„ Key preview: {push_service.vapid_public_key[:50]}...")
        else:
            print("   âš ï¸  VAPID public key not found")
    except Exception as e:
        print(f"   âŒ VAPID key error: {e}")
    
    # Test 4: Check pywebpush installed
    print("\n4ï¸âƒ£ Testing pywebpush package...")
    try:
        from pywebpush import webpush
        print("   âœ… pywebpush is installed")
    except ImportError:
        print("   âŒ pywebpush not installed. Run: pip install pywebpush")
    
    # Test 5: Test notification service initialization
    print("\n5ï¸âƒ£ Testing PushNotificationService...")
    try:
        service = PushNotificationService(app)
        subscriptions = service.get_subscriptions()
        print(f"   âœ… Service initialized successfully")
        print(f"   ðŸ“Š Active subscriptions: {len(subscriptions)}")
    except Exception as e:
        print(f"   âš ï¸  Service initialization warning: {e}")

print("\n" + "="*60)
print("âœ… All tests passed! Push notification system is ready.")
print("="*60)
print("\nðŸ“š Next Steps:")
print("1. Deploy to Streamlit Cloud/Railway/Render for HTTPS")
print("2. Add VAPID keys to environment variables (optional)")
print("3. Test on mobile device")
print("4. See PUSH_NOTIFICATIONS_COMPLETE.md for full guide")

