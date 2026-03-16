"""
Test script for push notification system.
Verifies core components are wired correctly.
"""

from app import create_app
from app.extensions import db
from app.models import AppSettings, PushSubscription
from app.push_notifications import PushNotificationService

app = create_app(start_scheduler=False)

print("Testing Push Notification System\n")

with app.app_context():
    print("1) Testing database setup...")
    try:
        subscription_count = PushSubscription.query.count()
        print(f"   OK: PushSubscription table exists ({subscription_count} subscriptions)")
    except Exception as e:
        print(f"   ERROR: Database error: {e}")
        raise SystemExit(1)

    print("\n2) Testing AppSettings...")
    try:
        settings = AppSettings.query.first()
        if settings:
            print("   OK: Settings found")
            print(f"   Notifications enabled: {settings.notifications_enabled}")
            print(f"   Min score to notify: {settings.min_score_to_notify}")
        else:
            print("   WARN: No settings found, creating defaults...")
            settings = AppSettings()
            db.session.add(settings)
            db.session.commit()
            print("   OK: Default settings created")
    except Exception as e:
        print(f"   ERROR: Settings error: {e}")
        raise SystemExit(1)

    print("\n3) Testing VAPID keys...")
    try:
        push_service = PushNotificationService(app)
        if push_service.vapid_private_key:
            print("   OK: VAPID private key loaded")
            print(f"   Key preview: {push_service.vapid_private_key[:50]}...")
        else:
            print("   WARN: VAPID private key not found")

        if push_service.vapid_public_key:
            print("   OK: VAPID public key loaded")
            print(f"   Key preview: {push_service.vapid_public_key[:50]}...")
        else:
            print("   WARN: VAPID public key not found")
    except Exception as e:
        print(f"   ERROR: VAPID key error: {e}")

    print("\n4) Testing pywebpush package...")
    try:
        from pywebpush import webpush  # noqa: F401

        print("   OK: pywebpush is installed")
    except ImportError:
        print("   ERROR: pywebpush not installed. Run: pip install pywebpush")

    print("\n5) Testing PushNotificationService...")
    try:
        service = PushNotificationService(app)
        subscriptions = service.get_subscriptions()
        print("   OK: Service initialized successfully")
        print(f"   Active subscriptions: {len(subscriptions)}")
    except Exception as e:
        print(f"   WARN: Service initialization warning: {e}")

print("\n" + "=" * 60)
print("All checks completed.")
print("=" * 60)
