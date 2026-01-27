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
        
        # Kenya-Specific Sources
        kenya_sources = [
            {
                "name": "UNDP Kenya Opportunities",
                "url": "https://www.ug.undp.org/tenders"
            },
            {
                "name": "World Bank Kenya Tenders",
                "url": "https://www.worldbank.org/en/projects-operations/products-and-services/brief/world-bank-tenders"
            },
            {
                "name": "USAID Kenya Procurement",
                "url": "https://www.usaid.gov/kenya"
            },
            {
                "name": "AfDB Tender Portal",
                "url": "https://www.afdb.org/en/projects/procurement/tenders"
            },
        ]
        
        # Global Sources
        global_sources = [
            {
                "name": "UNDB Global",
                "url": "https://www.undb.org/opportunities"
            },
            {
                "name": "GEF Procurement",
                "url": "https://www.thegef.org/council-meeting-documents/procurement"
            },
            {
                "name": "IFC Tenders",
                "url": "https://www.ifc.org/en/what-we-do/advisory-services"
            },
            {
                "name": "UNOPS Tenders",
                "url": "https://www.unops.org/who-we-are/our-office"
            },
        ]
        
        # Add all sources
        all_sources = kenya_sources + global_sources
        
        for source_data in all_sources:
            source = TenderSource(
                name=source_data["name"],
                url=source_data["url"],
                active=True,
                favorite=False
            )
            db.session.add(source)
        
        db.session.commit()
        print(f"✓ Added {len(all_sources)} tender sources")
        print(f"  - {len(kenya_sources)} Kenya-specific sources")
        print(f"  - {len(global_sources)} Global sources")

if __name__ == "__main__":
    init_sources()
