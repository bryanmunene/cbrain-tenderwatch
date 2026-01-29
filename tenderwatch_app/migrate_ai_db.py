"""
Database migration script to add AI/ML fields
Run this to update existing database schema
"""

from app import create_app
from app.extensions import db
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_database():
    """Add new AI fields to existing database"""
    app = create_app()
    
    with app.app_context():
        logger.info("🔄 Starting database migration for AI features...")
        
        migrations = [
            # Add AI fields to TenderResult
            ("ALTER TABLE tender_result ADD COLUMN semantic_score FLOAT DEFAULT 0.0", 
             "Add semantic_score column"),
            ("ALTER TABLE tender_result ADD COLUMN ai_confidence FLOAT DEFAULT 0.0", 
             "Add ai_confidence column"),
            ("ALTER TABLE tender_result ADD COLUMN entities_extracted TEXT DEFAULT ''", 
             "Add entities_extracted column"),
            ("ALTER TABLE tender_result ADD COLUMN ai_summary TEXT DEFAULT ''", 
             "Add ai_summary column"),
            
            # Add AI settings to AppSettings
            ("ALTER TABLE app_settings ADD COLUMN ai_scoring_enabled BOOLEAN DEFAULT 1", 
             "Add ai_scoring_enabled setting"),
            ("ALTER TABLE app_settings ADD COLUMN ai_learning_enabled BOOLEAN DEFAULT 1", 
             "Add ai_learning_enabled setting"),
            ("ALTER TABLE app_settings ADD COLUMN entity_extraction_enabled BOOLEAN DEFAULT 1", 
             "Add entity_extraction_enabled setting"),
        ]
        
        success_count = 0
        for sql, description in migrations:
            try:
                db.session.execute(text(sql))
                db.session.commit()
                logger.info(f"✅ {description}")
                success_count += 1
            except Exception as e:
                error_msg = str(e).lower()
                if 'duplicate column' in error_msg or 'already exists' in error_msg:
                    logger.info(f"⏭️  {description} - Already exists")
                else:
                    logger.error(f"❌ {description} - Failed: {e}")
                db.session.rollback()
        
        logger.info(f"\n✅ Migration complete! {success_count}/{len(migrations)} changes applied")
        logger.info("\n🎯 Next steps:")
        logger.info("1. Install AI libraries: pip install -r requirements.txt")
        logger.info("2. Download spaCy model: python -m spacy download en_core_web_sm")
        logger.info("3. Restart your app to use AI features")

if __name__ == "__main__":
    migrate_database()
