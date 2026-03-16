"""
TenderWatch Initialization Script
Adds vetted default tender sources (Kenya/Africa first, then global official).
"""

import json

from app import create_app
from app.extensions import db
from app.models import TenderSource


DEFAULT_SOURCES = [
    ("Kenya PPIP", "https://tenders.go.ke/website/tenders/all", "africa_priority"),
    ("ICT Authority", "https://icta.go.ke/tenders/", "africa_priority"),
    ("KEMSA Tenders", "https://www.kemsa.co.ke/tenders/", "africa_priority"),
    ("KRA Tenders", "https://www.kra.go.ke/en/tenders", "africa_priority"),
    ("KAA Procurement", "https://www.kaa.go.ke/business-opportunities/procurement/", "africa_priority"),
    ("KETRACO Tenders", "https://www.ketraco.co.ke/procurement/tenders/open-tenders", "africa_priority"),
    ("KPA Tenders", "https://kpa.co.ke/procurement/", "africa_priority"),
    ("Kenya Railways", "https://krc.co.ke/tenders/", "africa_priority"),
    ("NTSA Tenders", "https://ntsa.go.ke/tenders/", "africa_priority"),
    ("CAK Tenders", "https://cak.go.ke/tenders", "africa_priority"),
    ("CBK Tenders", "https://www.centralbank.go.ke/tenders/", "africa_priority"),
    ("NEMA Tenders", "https://www.nema.go.ke/index.php/tenders", "africa_priority"),
    ("South Africa eTender", "https://www.etenders.gov.za/", "africa_priority"),
    ("Uganda PPDA", "https://www.ppda.go.ug/", "africa_priority"),
    ("Tanzania PPRA", "https://www.ppra.go.tz/", "africa_priority"),
    ("Nigeria BPP", "https://www.bpp.gov.ng/", "africa_priority"),
    ("Nigeria BPP P-COMS", "https://pcoms.bpp.gov.ng/", "africa_priority"),
    ("Ghana PPA", "https://ppa.gov.gh/", "africa_priority"),
    ("GHANEPS", "https://www.ghaneps.gov.gh/", "africa_priority"),
    ("Zambia ZPPA", "https://www.zppa.org.zm/", "africa_priority"),
    ("Rwanda RPPA", "https://www.rppa.gov.rw/", "africa_priority"),
    ("TradeMark Africa Procurement", "https://trademarkafrica.com/procurement/", "africa_regional"),
    ("AfDB Procurement", "https://www.afdb.org/en/projects-and-operations/procurement", "africa_regional"),
    ("UNDP Procurement Notices", "https://procurement-notices.undp.org/", "global_multilateral"),
    ("UN Global Marketplace", "https://www.ungm.org/Public/Notice", "global_multilateral"),
    ("UNOPS Opportunities", "https://www.unops.org/business-opportunities", "global_multilateral"),
    ("World Bank Procurement", "https://projects.worldbank.org/en/projects-operations/procurement", "global_multilateral"),
    ("DevBusiness (World Bank)", "https://devbusiness.un.org/", "global_multilateral"),
    ("WHO Procurement", "https://www.who.int/about/accountability/procurement", "global_multilateral"),
    ("WFP Procurement", "https://www.wfp.org/procurement", "global_multilateral"),
    ("TED Europa Tenders", "https://ted.europa.eu/en/search/result", "global_public"),
    ("UK Find a Tender", "https://www.find-tender.service.gov.uk/Search", "global_public"),
    ("Denmark Udbud", "https://udbud.dk/", "global_public"),
    ("Germany BUND", "https://www.service.bund.de/Content/DE/Ausschreibungen/Suche/Formular.html", "global_public"),
    ("EU Funding & Tenders", "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-search", "global_public"),
    ("SAM.gov (US Federal)", "https://sam.gov/search/?index=opp&page=1&sort=-modifiedDate", "global_public"),
    ("Australia AusTender", "https://www.tenders.gov.au/", "global_public"),
    ("India CPPP", "https://eprocure.gov.in/eprocure/app", "global_public"),
    ("Singapore GeBIZ", "https://www.gebiz.gov.sg/", "global_public"),
    ("Commonwealth Secretariat Procurement", "https://thecommonwealth.org/procurement", "global_multilateral"),
    ("IDB Procurement Projects", "https://www.iadb.org/en/how-we-can-work-together/procurement/procurement-projects", "global_multilateral"),
    ("AIIB Project Procurement", "https://www.aiib.org/en/opportunities/business/project-procurement/index.html", "global_multilateral"),
    ("EIB Procurement Calls", "https://www.eib.org/en/about/procurement/all/index.htm", "global_multilateral"),
]


def init_sources():
    """Initialize default tender sources."""

    app = create_app(start_scheduler=False)

    with app.app_context():
        if TenderSource.query.first():
            print("Sources already initialized.")
            return

        for name, url, source_group in DEFAULT_SOURCES:
            db.session.add(
                TenderSource(
                    name=name,
                    url=url,
                    active=True,
                    favorite=False,
                    source_group=source_group,
                    source_tags=json.dumps([source_group]),
                )
            )

        db.session.commit()
        print(f"Added {len(DEFAULT_SOURCES)} tender sources")


if __name__ == "__main__":
    init_sources()
