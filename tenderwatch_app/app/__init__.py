import logging
import os
import secrets

from flask import Flask

from app.extensions import db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _load_env_file():
    """Load .env values if python-dotenv is available."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        # Optional dependency; environment can still be provided by platform.
        pass


def _initialize_database(app):
    """Create baseline schema, run lightweight migrations, and seed required rows."""
    with app.app_context():
        db.create_all()

        # Auto-migrate AI fields if they don't exist
        from sqlalchemy import inspect, text

        inspector = inspect(db.engine)

        try:
            # Check if AI columns exist, add if missing
            tender_columns = [col["name"] for col in inspector.get_columns("tender_result")]
            settings_columns = [col["name"] for col in inspector.get_columns("app_settings")]

            ai_migrations = []

            if "semantic_score" not in tender_columns:
                ai_migrations.append("ALTER TABLE tender_result ADD COLUMN semantic_score FLOAT DEFAULT 0.0")
            if "ai_confidence" not in tender_columns:
                ai_migrations.append("ALTER TABLE tender_result ADD COLUMN ai_confidence FLOAT DEFAULT 0.0")
            if "entities_extracted" not in tender_columns:
                ai_migrations.append("ALTER TABLE tender_result ADD COLUMN entities_extracted TEXT DEFAULT ''")
            if "ai_summary" not in tender_columns:
                ai_migrations.append("ALTER TABLE tender_result ADD COLUMN ai_summary TEXT DEFAULT ''")

            if "ai_scoring_enabled" not in settings_columns:
                ai_migrations.append("ALTER TABLE app_settings ADD COLUMN ai_scoring_enabled BOOLEAN DEFAULT 1")
            if "ai_learning_enabled" not in settings_columns:
                ai_migrations.append("ALTER TABLE app_settings ADD COLUMN ai_learning_enabled BOOLEAN DEFAULT 1")
            if "entity_extraction_enabled" not in settings_columns:
                ai_migrations.append("ALTER TABLE app_settings ADD COLUMN entity_extraction_enabled BOOLEAN DEFAULT 1")

            for migration_sql in ai_migrations:
                db.session.execute(text(migration_sql))

            if ai_migrations:
                db.session.commit()
                logger.info("Applied %s AI schema migrations", len(ai_migrations))

            # Check for push_subscription table, create if missing
            if "push_subscription" not in inspector.get_table_names():
                db.session.execute(
                    text(
                        """
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
                    """
                    )
                )
                db.session.commit()
                logger.info("Created push_subscription table")

        except Exception as e:
            logger.warning("Schema migration skipped: %s", e)
            db.session.rollback()

        # Initialize settings if not exist
        from app.models import AppSettings

        try:
            if not AppSettings.query.first():
                settings = AppSettings()
                settings.auto_discovery_enabled = False
                settings.google_api_key = ""
                settings.google_cx = ""
                settings.bing_api_key = ""
                db.session.add(settings)
                db.session.commit()
        except Exception as e:
            logger.error("Failed to initialize settings: %s", e)
            db.session.rollback()


def create_app(start_scheduler=False, init_db=True):
    _load_env_file()

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///tenderwatch.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        secret_key = secrets.token_hex(32)
        logger.warning("SECRET_KEY not set; using ephemeral key for this process.")
    app.config["SECRET_KEY"] = secret_key

    db.init_app(app)

    from app.routes import main

    app.register_blueprint(main)

    if init_db:
        _initialize_database(app)

    if start_scheduler:
        from app.scheduler import start_scheduler

        start_scheduler(app)

    return app
