"""
Database migration script for F2-aligned fields.
Adds new columns for F2 classification without losing existing data.
"""

from sqlalchemy import text
from app import create_app
from app.extensions import db

def migrate():
    """Add F2-aligned columns to tender_result table"""
    app = create_app()
    
    with app.app_context():
        # New F2 columns to add
        new_columns = [
            ("publication_date", "VARCHAR(200)", ""),
            ("inferred_domains", "TEXT", "[]"),
            ("priority_level", "VARCHAR(20)", "LOW"),
            ("likely_fit_for_f2", "VARCHAR(20)", "uncertain"),
            ("timing_status", "VARCHAR(100)", ""),
            ("procurement_status", "VARCHAR(20)", "open"),  # open, locked, locked_but_open
        ]
        
        for col_name, col_type, default in new_columns:
            try:
                # Check if column exists
                result = db.session.execute(
                    text(f"SELECT {col_name} FROM tender_result LIMIT 1")
                )
                print(f"✓ Column '{col_name}' already exists")
            except Exception:
                # Column doesn't exist, add it
                try:
                    default_clause = f"DEFAULT '{default}'" if default else ""
                    db.session.execute(
                        text(f"ALTER TABLE tender_result ADD COLUMN {col_name} {col_type} {default_clause}")
                    )
                    db.session.commit()
                    print(f"✓ Added column '{col_name}'")
                except Exception as e:
                    print(f"⚠️  Could not add column '{col_name}': {e}")
                    db.session.rollback()
        
        print("\n✅ F2-aligned migration complete!")


if __name__ == "__main__":
    migrate()
