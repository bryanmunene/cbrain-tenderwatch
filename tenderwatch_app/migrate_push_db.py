"""
Migration script for push notification subscriptions
Run this after updating models.py with PushSubscription model
"""
from app import create_app
from app.extensions import db
from sqlalchemy import text, inspect

app = create_app(start_scheduler=False)

with app.app_context():
    inspector = inspect(db.engine)
    
    print("ðŸ”„ Checking for push_subscription table...")
    
    if 'push_subscription' not in inspector.get_table_names():
        print("ðŸ“¦ Creating push_subscription table...")
        
        db.session.execute(text("""
            CREATE TABLE push_subscription (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint TEXT UNIQUE NOT NULL,
                p256dh_key TEXT NOT NULL,
                auth_key TEXT NOT NULL,
                user_agent TEXT DEFAULT '',
                active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_used DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        db.session.commit()
        print("âœ… Push subscription table created successfully!")
    else:
        print("âœ… Push subscription table already exists")
    
    # Verify min_score_to_notify column exists in app_settings
    settings_columns = [col['name'] for col in inspector.get_columns('app_settings')]
    
    if 'min_score_to_notify' not in settings_columns:
        print("ðŸ“¦ Adding min_score_to_notify column to app_settings...")
        db.session.execute(text(
            "ALTER TABLE app_settings ADD COLUMN min_score_to_notify FLOAT DEFAULT 50.0"
        ))
        db.session.commit()
        print("âœ… min_score_to_notify column added!")
    else:
        print("âœ… min_score_to_notify column already exists")
    
    print("\nâœ… Database migration complete!")

