"""
Database migration script to add new columns for autonomous features
Run this to update your existing database without losing data
"""
import sqlite3
import os

# Path to database
db_path = os.path.join(os.path.dirname(__file__), 'instance', 'tenderwatch.db')

if not os.path.exists(db_path):
    print("❌ Database not found. It will be created when you run the app.")
    exit(0)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("🔧 Updating database schema...")

# Check if columns already exist
cursor.execute("PRAGMA table_info(tender_result)")
columns = [col[1] for col in cursor.fetchall()]

# Add notified column to tender_result if not exists
if 'notified' not in columns:
    try:
        cursor.execute("ALTER TABLE tender_result ADD COLUMN notified BOOLEAN DEFAULT 0")
        print("✓ Added 'notified' column to tender_result")
    except Exception as e:
        print(f"✓ Column 'notified' already exists or error: {e}")

# Check if app_settings table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='app_settings'")
if not cursor.fetchone():
    try:
        cursor.execute("""
            CREATE TABLE app_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                auto_scan_enabled BOOLEAN DEFAULT 0,
                scan_interval_minutes INTEGER DEFAULT 60,
                notifications_enabled BOOLEAN DEFAULT 1,
                notify_desktop BOOLEAN DEFAULT 1,
                notify_email BOOLEAN DEFAULT 0,
                email_recipients TEXT DEFAULT '',
                smtp_server VARCHAR(200) DEFAULT 'smtp.gmail.com',
                smtp_port INTEGER DEFAULT 587,
                smtp_username VARCHAR(200) DEFAULT '',
                smtp_password VARCHAR(200) DEFAULT '',
                min_score_to_notify FLOAT DEFAULT 50.0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✓ Created 'app_settings' table")
        
        # Insert default settings
        cursor.execute("""
            INSERT INTO app_settings (
                auto_scan_enabled, scan_interval_minutes, notifications_enabled,
                notify_desktop, notify_email, min_score_to_notify
            ) VALUES (0, 60, 1, 1, 0, 50.0)
        """)
        print("✓ Inserted default settings")
    except Exception as e:
        print(f"✓ Table 'app_settings' already exists or error: {e}")
else:
    print("✓ Table 'app_settings' already exists")

# Commit changes
conn.commit()
conn.close()

print("\n✅ Database migration completed!")
print("Restart your Flask server now.")
