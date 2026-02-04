"""
Database Migration for Auto-Discovery Feature
==============================================
Adds new columns and tables to support auto-discovery via Google and Bing APIs.

Run this ONCE before using auto-discovery features.
"""

from app import create_app
from app.extensions import db
from sqlalchemy import text

def migrate_database():
    """Add auto-discovery fields to existing database"""
    app = create_app()
    
    with app.app_context():
        print("🔧 Starting auto-discovery database migration...")
        
        try:
            # Add discovery columns to TenderResult
            print("  ➜ Adding discovery_method column...")
            db.session.execute(text(
                "ALTER TABLE tender_result ADD COLUMN discovery_method VARCHAR(50) DEFAULT 'manual'"
            ))
            
            print("  ➜ Adding search_query column...")
            db.session.execute(text(
                "ALTER TABLE tender_result ADD COLUMN search_query VARCHAR(500)"
            ))
            
            print("  ➜ Adding search_source column...")
            db.session.execute(text(
                "ALTER TABLE tender_result ADD COLUMN search_source VARCHAR(50)"
            ))
            
            # Add auto-discovery settings to AppSettings
            print("  ➜ Adding auto_discovery_enabled column...")
            db.session.execute(text(
                "ALTER TABLE app_settings ADD COLUMN auto_discovery_enabled BOOLEAN DEFAULT 1"
            ))
            
            print("  ➜ Adding google_api_key column...")
            db.session.execute(text(
                "ALTER TABLE app_settings ADD COLUMN google_api_key VARCHAR(500) DEFAULT ''"
            ))
            
            print("  ➜ Adding google_cx column...")
            db.session.execute(text(
                "ALTER TABLE app_settings ADD COLUMN google_cx VARCHAR(500) DEFAULT ''"
            ))
            
            print("  ➜ Adding bing_api_key column...")
            db.session.execute(text(
                "ALTER TABLE app_settings ADD COLUMN bing_api_key VARCHAR(500) DEFAULT ''"
            ))
            
            print("  ➜ Adding discovery_queries column...")
            db.session.execute(text(
                "ALTER TABLE app_settings ADD COLUMN discovery_queries TEXT DEFAULT ''"
            ))
            
            print("  ➜ Adding results_per_query column...")
            db.session.execute(text(
                "ALTER TABLE app_settings ADD COLUMN results_per_query INTEGER DEFAULT 10"
            ))
            
            # Create DiscoveryLog table
            print("  ➜ Creating discovery_log table...")
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS discovery_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_type VARCHAR(50) NOT NULL,
                    queries_run INTEGER DEFAULT 0,
                    results_found INTEGER DEFAULT 0,
                    results_saved INTEGER DEFAULT 0,
                    google_quota_used INTEGER DEFAULT 0,
                    bing_quota_used INTEGER DEFAULT 0,
                    execution_time_seconds REAL DEFAULT 0.0,
                    error_message TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            db.session.commit()
            print("✅ Migration complete! Auto-discovery is ready to use.")
            print("\n📝 Next steps:")
            print("   1. Get API keys (see AUTO_DISCOVERY_SETUP.md)")
            print("   2. Configure in Settings → Auto-Discovery")
            print("   3. Visit /discovery to view dashboard")
            
        except Exception as e:
            error_str = str(e)
            if "duplicate column" in error_str.lower() or "already exists" in error_str.lower():
                print("ℹ️  Migration already applied (columns exist)")
                db.session.rollback()
            else:
                print(f"❌ Migration failed: {e}")
                db.session.rollback()
                raise

if __name__ == "__main__":
    migrate_database()
