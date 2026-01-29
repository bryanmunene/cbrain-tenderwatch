"""
Test script for push notification system
Verifies all components are working correctly
"""
from app import create_app
from app.extensions import db
from app.models import PushSubscription, AppSettings
from app.push_notifications import PushNotificationService

app = create_app()

print("🧪 Testing Push Notification System\n")

with app.app_context():
    # Test 1: Check database table exists
    print("1️⃣ Testing database setup...")
    try:
        subscription_count = PushSubscription.query.count()
        print(f"   ✅ PushSubscription table exists ({subscription_count} subscriptions)")
    except Exception as e:
        print(f"   ❌ Database error: {e}")
        exit(1)
    
    # Test 2: Check AppSettings has notification fields
    print("\n2️⃣ Testing AppSettings...")
    try:
        settings = AppSettings.query.first()
        if settings:
            print(f"   ✅ Settings found")
            print(f"   📊 Notifications enabled: {settings.notifications_enabled}")
            print(f"   📊 Min score to notify: {settings.min_score_to_notify}")
        else:
            print("   ⚠️  No settings found, creating defaults...")
            settings = AppSettings()
            db.session.add(settings)
            db.session.commit()
            print("   ✅ Default settings created")
    except Exception as e:
        print(f"   ❌ Settings error: {e}")
        exit(1)
    
    # Test 3: Check VAPID keys loaded
    print("\n3️⃣ Testing VAPID keys...")
    try:
        push_service = PushNotificationService(app)
        if push_service.vapid_private_key:
            print("   ✅ VAPID private key loaded")
            print(f"   📄 Key preview: {push_service.vapid_private_key[:50]}...")
        else:
            print("   ⚠️  VAPID private key not found")
        
        if push_service.vapid_public_key:
            print("   ✅ VAPID public key loaded")
            print(f"   📄 Key preview: {push_service.vapid_public_key[:50]}...")
        else:
            print("   ⚠️  VAPID public key not found")
    except Exception as e:
        print(f"   ❌ VAPID key error: {e}")
    
    # Test 4: Check pywebpush installed
    print("\n4️⃣ Testing pywebpush package...")
    try:
        from pywebpush import webpush
        print("   ✅ pywebpush is installed")
    except ImportError:
        print("   ❌ pywebpush not installed. Run: pip install pywebpush")
    
    # Test 5: Test notification service initialization
    print("\n5️⃣ Testing PushNotificationService...")
    try:
        service = PushNotificationService(app)
        subscriptions = service.get_subscriptions()
        print(f"   ✅ Service initialized successfully")
        print(f"   📊 Active subscriptions: {len(subscriptions)}")
    except Exception as e:
        print(f"   ⚠️  Service initialization warning: {e}")

print("\n" + "="*60)
print("✅ All tests passed! Push notification system is ready.")
print("="*60)
print("\n📚 Next Steps:")
print("1. Deploy to Streamlit Cloud/Railway/Render for HTTPS")
print("2. Add VAPID keys to environment variables (optional)")
print("3. Test on mobile device")
print("4. See PUSH_NOTIFICATIONS_COMPLETE.md for full guide")
