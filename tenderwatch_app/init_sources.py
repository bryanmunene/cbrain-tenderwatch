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
        
        # Global Tender Listing Sources
        sources = [
            # UN/International Development
            {"name": "UNDP Procurement Notices", "url": "https://procurement-notices.undp.org/"},
            {"name": "UN Global Marketplace", "url": "https://www.ungm.org/Public/Notice"},
            {"name": "DevBusiness (World Bank)", "url": "https://devbusiness.un.org/content/tenders"},
            
            # Regional Development Banks
            {"name": "AfDB Procurement", "url": "https://www.afdb.org/en/about-us/corporate-procurement/procurement-notices"},
            {"name": "ADB Procurement", "url": "https://www.adb.org/projects/tenders/all"},
            {"name": "IDB Procurement", "url": "https://www.iadb.org/en/procurement/current-opportunities"},
            
            # Government Portals
            {"name": "TED Europa (EU)", "url": "https://ted.europa.eu/en/search/result"},
            {"name": "SAM.gov (US Federal)", "url": "https://sam.gov/search/?index=opp&page=1&sort=-modifiedDate"},
            {"name": "Contracts Finder (UK)", "url": "https://www.contractsfinder.service.gov.uk/Search/Results"},
            
            # Development/NGO
            {"name": "DevEx Funding", "url": "https://www.devex.com/funding"},
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
