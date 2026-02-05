"""
TenderWatch Initialization Script
Adds default tender sources for Kenya and global opportunities
"""

from app import create_app
from app.extensions import db
from app.models import TenderSource

# Comprehensive global tender sources
DEFAULT_SOURCES = [
    # UN System
    ("UNDP Procurement", "https://procurement-notices.undp.org/"),
    ("UN Global Marketplace", "https://www.ungm.org/Public/Notice"),
    ("UNICEF Supply", "https://www.unicef.org/supply/procurement-services"),
    ("WHO Procurement", "https://www.who.int/about/accountability/procurement"),
    ("WFP Procurement", "https://www.wfp.org/procurement"),
    ("UNOPS Opportunities", "https://www.unops.org/business-opportunities"),
    ("UNESCO Procurement", "https://en.unesco.org/procurement"),
    ("FAO Procurement", "https://www.fao.org/unfao/procurement/"),
    
    # Development Banks
    ("World Bank Procurement", "https://projects.worldbank.org/en/projects-operations/procurement"),
    ("DevBusiness (World Bank)", "https://devbusiness.un.org/content/tenders"),
    ("AfDB Procurement", "https://www.afdb.org/en/about-us/corporate-procurement/procurement-notices"),
    ("ADB Procurement", "https://www.adb.org/projects/tenders/all"),
    ("IDB Procurement", "https://www.iadb.org/en/procurement/current-opportunities"),
    ("EBRD Procurement", "https://www.ebrd.com/work-with-us/procurement.html"),
    ("EIB Procurement", "https://www.eib.org/en/about/procurement/index.htm"),
    ("IsDB Procurement", "https://www.isdb.org/procurement"),
    
    # European Union
    ("TED Europa", "https://ted.europa.eu/en/search/result"),
    ("EU Funding Tenders", "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-search"),
    
    # Government Portals - Europe
    ("UK Contracts Finder", "https://www.contractsfinder.service.gov.uk/Search/Results"),
    ("UK Find a Tender", "https://www.find-tender.service.gov.uk/Search"),
    ("Germany BUND", "https://www.service.bund.de/Content/DE/Ausschreibungen/"),
    ("France BOAMP", "https://www.boamp.fr/pages/recherche/"),
    ("Netherlands TenderNed", "https://www.tenderned.nl/tenderned-tap/aankondigingen"),
    
    # Government Portals - Americas
    ("SAM.gov (US Federal)", "https://sam.gov/search/?index=opp&page=1&sort=-modifiedDate"),
    ("Canada Buyandsell", "https://buyandsell.gc.ca/procurement-data/tenders"),
    
    # Government Portals - Africa
    ("Kenya PPB", "https://tenders.go.ke/"),
    ("South Africa eTender", "https://www.etenders.gov.za/"),
    ("Nigeria BPP", "https://www.bpp.gov.ng/"),
    ("Ghana PPA", "https://ppaghana.org/tenders.asp"),
    ("Tanzania PPRA", "https://www.ppra.go.tz/"),
    ("Uganda PPDA", "https://www.ppda.go.ug/"),
    ("Rwanda RPPA", "https://umucyo.gov.rw/"),
    ("Ethiopia PPA", "https://ppa.gov.et/"),
    
    # Kenya Parastatals (Priority - ICT/EDRMS tenders)
    ("KAA Procurement", "https://www.kaa.go.ke/corporate/procurement/"),  # Kenya Airports Authority
    ("Kenya Railways", "https://krc.co.ke/tenders/"),
    ("KETRACO Tenders", "https://www.ketraco.co.ke/tenders/"),
    ("KenGen Tenders", "https://www.kengen.co.ke/index.php/procurement.html"),
    ("KEBS Tenders", "https://www.kebs.org/index.php?option=com_content&view=article&id=190"),
    ("NTSA Tenders", "https://www.ntsa.go.ke/tenders/"),
    ("KEMSA Tenders", "https://www.kemsa.co.ke/tenders/"),
    ("KPA Tenders", "https://www.kpa.co.ke/Tenders/Pages/default.aspx"),
    ("NEMA Tenders", "https://www.nema.go.ke/index.php/tenders"),
    ("CAK Tenders", "https://cak.go.ke/tenders"),
    ("ICT Authority", "https://icta.go.ke/tenders/"),
    
    # Government Portals - Asia Pacific
    ("Australia AusTender", "https://www.tenders.gov.au/"),
    ("New Zealand GETS", "https://www.gets.govt.nz/ExternalIndex.htm"),
    ("India CPPP", "https://eprocure.gov.in/eprocure/app"),
    ("Philippines PhilGEPS", "https://www.philgeps.gov.ph/"),
    ("Singapore GeBIZ", "https://www.gebiz.gov.sg/"),
    
    # International Organizations
    ("NATO Procurement", "https://www.nspa.nato.int/business"),
    ("Commonwealth Secretariat", "https://thecommonwealth.org/procurement"),
    
    # Development/NGO Portals
    ("DevEx Funding", "https://www.devex.com/funding"),
    ("ReliefWeb Jobs", "https://reliefweb.int/jobs"),
    
    # Tender Aggregators
    ("DgMarket", "https://www.dgmarket.com/"),
    ("Global Tenders", "https://www.globaltenders.com/"),
]

def init_sources():
    """Initialize default tender sources"""
    
    app = create_app()
    
    with app.app_context():
        # Check if sources already exist
        existing = TenderSource.query.first()
        if existing:
            print("Sources already initialized.")
            return
        
        # Add all sources
        for name, url in DEFAULT_SOURCES:
            source = TenderSource(name=name, url=url, active=True, favorite=False)
            db.session.add(source)
        
        db.session.commit()
        print(f"✓ Added {len(DEFAULT_SOURCES)} tender sources")

if __name__ == "__main__":
    init_sources()
