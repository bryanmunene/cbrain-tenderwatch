"""
TenderWatch Initialization Script
Adds default tender sources for Kenya and global opportunities
"""

from app import create_app
from app.extensions import db
from app.models import TenderSource

def init_sources():
    """Initialize default tender sources"""
    
    app = create_app()
    
    with app.app_context():
        # Check if sources already exist
        existing = TenderSource.query.first()
        if existing:
            print("Sources already initialized.")
            return
        
        # Real Tender Listing Sources
        sources = [
            {
                "name": "UNDP Procurement Notices",
                "url": "https://procurement-notices.undp.org/"
            },
            {
                "name": "UN Global Marketplace",
                "url": "https://www.ungm.org/Public/Notice"
            },
            {
                "name": "AfDB Procurement Notices",
                "url": "https://www.afdb.org/en/about-us/corporate-procurement/procurement-notices"
            },
            {
                "name": "DevBusiness (World Bank)",
                "url": "https://devbusiness.un.org/content/tenders"
            },
            {
                "name": "TED Europa (EU Tenders)",
                "url": "https://ted.europa.eu/TED/browse/browseByMap.do"
            },
            {
                "name": "UNOPS Procurement",
                "url": "https://www.unops.org/business-opportunities/procurement"
            },
        ]
        
        # Add all sources
        for source_data in sources:
            source = TenderSource(
                name=source_data["name"],
                url=source_data["url"],
                active=True,
                favorite=False
            )
            db.session.add(source)
        
        db.session.commit()
        print(f"✓ Added {len(sources)} tender sources")

if __name__ == "__main__":
    init_sources()
