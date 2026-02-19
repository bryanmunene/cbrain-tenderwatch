"""
TenderWatch Initialization Script
Adds vetted default tender sources (Kenya/Africa first, then global official).
"""

from app import create_app
from app.extensions import db
from app.models import TenderSource

# Curated official tender sources.
DEFAULT_SOURCES = [
    # Kenya (primary market)
    ("Kenya PPIP", "https://tenders.go.ke/website/tenders/all"),
    ("ICT Authority", "https://icta.go.ke/tenders/"),
    ("KEMSA Tenders", "https://www.kemsa.co.ke/tenders/"),
    ("KRA Tenders", "https://www.kra.go.ke/en/tenders"),
    ("KAA Procurement", "https://www.kaa.go.ke/business-opportunities/procurement/"),
    ("KETRACO Tenders", "https://www.ketraco.co.ke/procurement/tenders/open-tenders"),
    ("KPA Tenders", "https://kpa.co.ke/procurement/"),
    ("Kenya Railways", "https://krc.co.ke/tenders/"),
    ("NTSA Tenders", "https://ntsa.go.ke/tenders/"),
    ("CAK Tenders", "https://cak.go.ke/tenders"),
    ("CBK Tenders", "https://www.centralbank.go.ke/tenders/"),
    ("NEMA Tenders", "https://www.nema.go.ke/index.php/tenders"),

    # Africa focus
    ("South Africa eTender", "https://www.etenders.gov.za/"),
    ("Uganda PPDA", "https://www.ppda.go.ug/"),
    ("Tanzania PPRA", "https://www.ppra.go.tz/"),
    ("Nigeria BPP", "https://www.bpp.gov.ng/"),
    ("Nigeria BPP P-COMS", "https://pcoms.bpp.gov.ng/"),
    ("Ghana PPA", "https://ppa.gov.gh/"),
    ("GHANEPS", "https://www.ghaneps.gov.gh/"),
    ("Zambia ZPPA", "https://www.zppa.org.zm/"),
    ("Rwanda RPPA", "https://www.rppa.gov.rw/"),
    ("TradeMark Africa Procurement", "https://trademarkafrica.com/procurement/"),
    ("AfDB Procurement", "https://www.afdb.org/en/projects-and-operations/procurement"),

    # Global official portals
    ("UNDP Procurement Notices", "https://procurement-notices.undp.org/"),
    ("UN Global Marketplace", "https://www.ungm.org/Public/Notice"),
    ("UNOPS Opportunities", "https://www.unops.org/business-opportunities"),
    ("World Bank Procurement", "https://projects.worldbank.org/en/projects-operations/procurement"),
    ("DevBusiness (World Bank)", "https://devbusiness.un.org/"),
    ("WHO Procurement", "https://www.who.int/about/accountability/procurement"),
    ("WFP Procurement", "https://www.wfp.org/procurement"),
    ("TED Europa Tenders", "https://ted.europa.eu/en/search/result"),
    ("UK Find a Tender", "https://www.find-tender.service.gov.uk/Search"),
    ("Denmark Udbud", "https://udbud.dk/"),
    ("Germany BUND", "https://www.service.bund.de/Content/DE/Ausschreibungen/Suche/Formular.html"),
    ("EU Funding & Tenders", "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-search"),
    ("SAM.gov (US Federal)", "https://sam.gov/search/?index=opp&page=1&sort=-modifiedDate"),
    ("Australia AusTender", "https://www.tenders.gov.au/"),
    ("India CPPP", "https://eprocure.gov.in/eprocure/app"),
    ("Singapore GeBIZ", "https://www.gebiz.gov.sg/"),
    ("Commonwealth Secretariat Procurement", "https://thecommonwealth.org/procurement"),
    ("IDB Procurement Projects", "https://www.iadb.org/en/how-we-can-work-together/procurement/procurement-projects"),
    ("AIIB Project Procurement", "https://www.aiib.org/en/opportunities/business/project-procurement/index.html"),
    ("EIB Procurement Calls", "https://www.eib.org/en/about/procurement/all/index.htm"),
]


def init_sources():
    """Initialize default tender sources"""

    app = create_app(start_scheduler=False)

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
        print(f"Added {len(DEFAULT_SOURCES)} tender sources")


if __name__ == "__main__":
    init_sources()
