"""
Delete ALL manual tender sources from database
"""

from app import create_app
from app.extensions import db
from app.models import TenderSource

app = create_app()

with app.app_context():
    # Delete all sources
    count = TenderSource.query.count()
    print(f"Found {count} sources in database")
    
    if count > 0:
        TenderSource.query.delete()
        db.session.commit()
        print(f"✅ Deleted all {count} sources")
    else:
        print("✅ No sources to delete")
    
    # Verify
    remaining = TenderSource.query.count()
    print(f"Sources remaining: {remaining}")
