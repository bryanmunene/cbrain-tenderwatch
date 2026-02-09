from flask import Flask
from app.extensions import db
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///tenderwatch.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = "dev"

    db.init_app(app)

    from app.routes import main
    app.register_blueprint(main)

    with app.app_context():
        db.create_all()
        
        # Auto-migrate AI fields if they don't exist
        from sqlalchemy import text, inspect
        inspector = inspect(db.engine)
        
        try:
            # Check if AI columns exist, add if missing
            tender_columns = [col['name'] for col in inspector.get_columns('tender_result')]
            settings_columns = [col['name'] for col in inspector.get_columns('app_settings')]
            
            ai_migrations = []
            
            if 'semantic_score' not in tender_columns:
                ai_migrations.append("ALTER TABLE tender_result ADD COLUMN semantic_score FLOAT DEFAULT 0.0")
            if 'ai_confidence' not in tender_columns:
                ai_migrations.append("ALTER TABLE tender_result ADD COLUMN ai_confidence FLOAT DEFAULT 0.0")
            if 'entities_extracted' not in tender_columns:
                ai_migrations.append("ALTER TABLE tender_result ADD COLUMN entities_extracted TEXT DEFAULT ''")
            if 'ai_summary' not in tender_columns:
                ai_migrations.append("ALTER TABLE tender_result ADD COLUMN ai_summary TEXT DEFAULT ''")
            
            if 'ai_scoring_enabled' not in settings_columns:
                ai_migrations.append("ALTER TABLE app_settings ADD COLUMN ai_scoring_enabled BOOLEAN DEFAULT 1")
            if 'ai_learning_enabled' not in settings_columns:
                ai_migrations.append("ALTER TABLE app_settings ADD COLUMN ai_learning_enabled BOOLEAN DEFAULT 1")
            if 'entity_extraction_enabled' not in settings_columns:
                ai_migrations.append("ALTER TABLE app_settings ADD COLUMN entity_extraction_enabled BOOLEAN DEFAULT 1")
            
            for migration_sql in ai_migrations:
                db.session.execute(text(migration_sql))
            
            if ai_migrations:
                db.session.commit()
                logging.info(f"✅ Applied {len(ai_migrations)} AI schema migrations")
            
            # Check for push_subscription table, create if missing
            if 'push_subscription' not in inspector.get_table_names():
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
                logging.info("✅ Created push_subscription table")
                
        except Exception as e:
            logging.warning(f"Schema migration skipped: {e}")
            db.session.rollback()
        
        # Initialize settings if not exist
        from app.models import AppSettings
        try:
            if not AppSettings.query.first():
                settings = AppSettings()
                db.session.add(settings)
                db.session.commit()
        except Exception as e:
            logging.error(f"Failed to initialize settings: {e}")
            db.session.rollback()

    # Start scheduler if enabled
    from app.scheduler import start_scheduler
    start_scheduler(app)


    return app

# Expose the app instance for imports
app = create_app()
