import json
import logging
import os
import secrets

from flask import Flask, abort, request, session
from markupsafe import Markup

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
        # Ensure all model metadata is registered before create_all.
        import app.models  # noqa: F401
        from app.geography import infer_source_group, source_tags_for_group
        from app.models import AppSettings, TenderSource

        db.create_all()

        # Auto-migrate AI fields if they don't exist
        from sqlalchemy import inspect, text

        inspector = inspect(db.engine)

        try:
            # Check if AI columns exist, add if missing
            tender_columns = [col["name"] for col in inspector.get_columns("tender_result")]
            settings_columns = [col["name"] for col in inspector.get_columns("app_settings")]
            source_columns = [col["name"] for col in inspector.get_columns("tender_source")]

            ai_migrations = []

            if "semantic_score" not in tender_columns:
                ai_migrations.append("ALTER TABLE tender_result ADD COLUMN semantic_score FLOAT DEFAULT 0.0")
            if "ai_confidence" not in tender_columns:
                ai_migrations.append("ALTER TABLE tender_result ADD COLUMN ai_confidence FLOAT DEFAULT 0.0")
            if "entities_extracted" not in tender_columns:
                ai_migrations.append("ALTER TABLE tender_result ADD COLUMN entities_extracted TEXT DEFAULT ''")
            if "ai_summary" not in tender_columns:
                ai_migrations.append("ALTER TABLE tender_result ADD COLUMN ai_summary TEXT DEFAULT ''")
            if "ranking_score" not in tender_columns:
                ai_migrations.append("ALTER TABLE tender_result ADD COLUMN ranking_score FLOAT DEFAULT 0.0")
            if "source_group" not in tender_columns:
                ai_migrations.append("ALTER TABLE tender_result ADD COLUMN source_group VARCHAR(50) DEFAULT 'experimental'")
            if "scan_pipeline" not in tender_columns:
                ai_migrations.append("ALTER TABLE tender_result ADD COLUMN scan_pipeline VARCHAR(50) DEFAULT 'africa_priority'")
            if "geographic_scope" not in tender_columns:
                ai_migrations.append("ALTER TABLE tender_result ADD COLUMN geographic_scope VARCHAR(30) DEFAULT 'Unknown'")
            if "region" not in tender_columns:
                ai_migrations.append("ALTER TABLE tender_result ADD COLUMN region VARCHAR(100) DEFAULT ''")
            if "africa_priority_flag" not in tender_columns:
                ai_migrations.append("ALTER TABLE tender_result ADD COLUMN africa_priority_flag BOOLEAN DEFAULT 0")
            if "donor_or_multilateral_flag" not in tender_columns:
                ai_migrations.append("ALTER TABLE tender_result ADD COLUMN donor_or_multilateral_flag BOOLEAN DEFAULT 0")
            if "target_beneficiary_region" not in tender_columns:
                ai_migrations.append("ALTER TABLE tender_result ADD COLUMN target_beneficiary_region VARCHAR(100) DEFAULT ''")
            if "buyer_region" not in tender_columns:
                ai_migrations.append("ALTER TABLE tender_result ADD COLUMN buyer_region VARCHAR(100) DEFAULT ''")
            if "implementation_region" not in tender_columns:
                ai_migrations.append("ALTER TABLE tender_result ADD COLUMN implementation_region VARCHAR(100) DEFAULT ''")
            if "recommendation" not in tender_columns:
                ai_migrations.append("ALTER TABLE tender_result ADD COLUMN recommendation VARCHAR(20) DEFAULT 'REVIEW'")
            if "queue_bucket" not in tender_columns:
                ai_migrations.append("ALTER TABLE tender_result ADD COLUMN queue_bucket VARCHAR(30) DEFAULT 'main_shortlist'")

            if "source_group" not in source_columns:
                ai_migrations.append("ALTER TABLE tender_source ADD COLUMN source_group VARCHAR(50) DEFAULT 'experimental'")
            if "source_tags" not in source_columns:
                ai_migrations.append("ALTER TABLE tender_source ADD COLUMN source_tags TEXT DEFAULT '[]'")

            if "ai_scoring_enabled" not in settings_columns:
                ai_migrations.append("ALTER TABLE app_settings ADD COLUMN ai_scoring_enabled BOOLEAN DEFAULT 1")
            if "ai_learning_enabled" not in settings_columns:
                ai_migrations.append("ALTER TABLE app_settings ADD COLUMN ai_learning_enabled BOOLEAN DEFAULT 1")
            if "entity_extraction_enabled" not in settings_columns:
                ai_migrations.append("ALTER TABLE app_settings ADD COLUMN entity_extraction_enabled BOOLEAN DEFAULT 1")
            if "africa_priority_weight" not in settings_columns:
                ai_migrations.append("ALTER TABLE app_settings ADD COLUMN africa_priority_weight FLOAT DEFAULT 12.0")
            if "global_relevance_threshold" not in settings_columns:
                ai_migrations.append("ALTER TABLE app_settings ADD COLUMN global_relevance_threshold FLOAT DEFAULT 28.0")
            if "donor_multilateral_boost" not in settings_columns:
                ai_migrations.append("ALTER TABLE app_settings ADD COLUMN donor_multilateral_boost FLOAT DEFAULT 8.0")
            if "africa_only_mode" not in settings_columns:
                ai_migrations.append("ALTER TABLE app_settings ADD COLUMN africa_only_mode BOOLEAN DEFAULT 0")
            if "include_global_sources" not in settings_columns:
                ai_migrations.append("ALTER TABLE app_settings ADD COLUMN include_global_sources BOOLEAN DEFAULT 1")
            if "include_global_in_default_shortlist" not in settings_columns:
                ai_migrations.append("ALTER TABLE app_settings ADD COLUMN include_global_in_default_shortlist BOOLEAN DEFAULT 0")
            if "secondary_review_queue_threshold" not in settings_columns:
                ai_migrations.append("ALTER TABLE app_settings ADD COLUMN secondary_review_queue_threshold FLOAT DEFAULT 16.0")

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
        try:
            if not AppSettings.query.first():
                settings = AppSettings()
                settings.auto_discovery_enabled = False
                settings.google_api_key = ""
                settings.google_cx = ""
                settings.bing_api_key = ""
                settings.africa_priority_weight = 12.0
                settings.global_relevance_threshold = 28.0
                settings.donor_multilateral_boost = 8.0
                settings.africa_only_mode = False
                settings.include_global_sources = True
                settings.include_global_in_default_shortlist = False
                settings.secondary_review_queue_threshold = 16.0
                db.session.add(settings)
                db.session.commit()
            else:
                settings = AppSettings.query.first()
                settings.africa_priority_weight = float(settings.africa_priority_weight or 12.0)
                settings.global_relevance_threshold = float(settings.global_relevance_threshold or 28.0)
                settings.donor_multilateral_boost = float(settings.donor_multilateral_boost or 8.0)
                settings.secondary_review_queue_threshold = float(settings.secondary_review_queue_threshold or 16.0)
                if settings.global_relevance_threshold == 60.0 and settings.secondary_review_queue_threshold == 45.0:
                    settings.global_relevance_threshold = 28.0
                    settings.secondary_review_queue_threshold = 16.0
                if settings.include_global_sources is None:
                    settings.include_global_sources = True
                if settings.include_global_in_default_shortlist is None:
                    settings.include_global_in_default_shortlist = False
                if settings.africa_only_mode is None:
                    settings.africa_only_mode = False
                db.session.commit()

            sources = TenderSource.query.all()
            dirty = False
            for source in sources:
                inferred_group = infer_source_group(
                    source_name=source.name,
                    source_url=source.url,
                    explicit_group=getattr(source, "source_group", "") or "",
                    explicit_tags=getattr(source, "source_tags", "") or "",
                )
                if getattr(source, "source_group", "") != inferred_group:
                    source.source_group = inferred_group
                    dirty = True
                expected_tags = source_tags_for_group(inferred_group)
                existing_tags = getattr(source, "source_tags", "") or ""
                if existing_tags != json.dumps(expected_tags):
                    source.source_tags = json.dumps(expected_tags)
                    dirty = True
            if dirty:
                db.session.commit()
        except Exception as e:
            logger.error("Failed to initialize settings: %s", e)
            db.session.rollback()


def create_app(start_scheduler=False, init_db=True):
    _load_env_file()

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///tenderwatch.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["ENABLE_INTERNAL_SCHEDULER"] = bool(start_scheduler)

    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        secret_key = secrets.token_hex(32)
        logger.warning("SECRET_KEY not set; using ephemeral key for this process.")
    app.config["SECRET_KEY"] = secret_key

    db.init_app(app)

    def _ensure_csrf_token():
        token = session.get("_csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["_csrf_token"] = token
        return token

    @app.before_request
    def _protect_post_requests():
        if request.method != "POST":
            return

        expected = session.get("_csrf_token")
        provided = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
        if not expected or not provided or not secrets.compare_digest(expected, provided):
            abort(400, description="CSRF token missing or invalid.")

    @app.context_processor
    def _inject_template_helpers():
        def csrf_token():
            return _ensure_csrf_token()

        def csrf_field():
            token = _ensure_csrf_token()
            return Markup(f'<input type="hidden" name="csrf_token" value="{token}">')

        return {
            "csrf_token": csrf_token,
            "csrf_field": csrf_field,
        }

    from app.routes import main

    app.register_blueprint(main)

    if init_db:
        _initialize_database(app)

    if start_scheduler:
        from app.scheduler import start_scheduler

        start_scheduler(app)

    return app


# Explicitly export public API
__all__ = ["create_app", "db"]
