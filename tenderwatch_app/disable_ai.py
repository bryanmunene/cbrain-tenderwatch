"""Disable AI features without removing code"""
from app import create_app
from app.extensions import db
from app.models import AppSettings

app = create_app()

with app.app_context():
    settings = AppSettings.query.first()
    if settings:
        settings.ai_scoring_enabled = False
        settings.ai_learning_enabled = False
        settings.entity_extraction_enabled = False
        db.session.commit()
        print("✅ AI features disabled")
        print(f"   - Semantic scoring: {settings.ai_scoring_enabled}")
        print(f"   - Adaptive learning: {settings.ai_learning_enabled}")
        print(f"   - Entity extraction: {settings.entity_extraction_enabled}")
    else:
        print("❌ No settings found")
