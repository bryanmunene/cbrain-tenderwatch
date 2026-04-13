"""
TenderWatch Initialization Script
Adds vetted default tender sources (Kenya/Africa first, then global official).
"""

import json

from app import create_app  # type: ignore[attr-defined]
from app.extensions import db  # type: ignore[attr-defined]
from app.models import TenderSource  # type: ignore[attr-defined]


DEFAULT_SOURCES = [
    # ========== KENYA - PRIORITY SOURCES ==========
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
    ("Public Service Commission", "https://www.psc.go.ke/tenders/", "africa_priority"),
    ("Kenya Bureau of Standards", "https://www.kebs.org/procurement/tenders/", "africa_priority"),
    ("Energy & Petroleum Regulatory", "https://www.epra.go.ke/tenders/", "africa_priority"),
    ("Communications Authority", "https://ca.go.ke/tenders/", "africa_priority"),
    ("Nairobi City County", "https://nairobi.go.ke/tenders/", "africa_priority"),
    
    # ========== EAST AFRICA REGIONAL ==========
    ("South Africa eTender", "https://www.etenders.gov.za/", "africa_priority"),
    ("Uganda PPDA", "https://www.ppda.go.ug/", "africa_priority"),
    ("Tanzania PPRA", "https://www.ppra.go.tz/", "africa_priority"),
    ("Rwanda RPPA", "https://www.rppa.gov.rw/", "africa_priority"),
    ("Botswana PPADB", "https://www.ppadb.bw/", "africa_regional"),
    ("Malawi PPDA", "https://www.ppda.mw/", "africa_regional"),
    
    # ========== WEST & CENTRAL AFRICA ==========
    ("Nigeria BPP", "https://www.bpp.gov.ng/", "africa_priority"),
    ("Nigeria BPP P-COMS", "https://pcoms.bpp.gov.ng/", "africa_priority"),
    ("Ghana PPA", "https://ppa.gov.gh/", "africa_regional"),
    ("GHANEPS", "https://www.ghaneps.gov.gh/", "africa_regional"),
    ("Zambia ZPPA", "https://www.zppa.org.zm/", "africa_regional"),
    ("Cote d'Ivoire Marchés Publics", "https://www.marchespublics.gouv.ci/", "africa_regional"),
    ("Cameroon Marchés", "https://www.marchespublics.cm/", "africa_regional"),
    
    # ========== AFRICA - CONTINENTAL & MULTILATERAL ==========
    ("TradeMark Africa Procurement", "https://trademarkafrica.com/procurement/", "africa_regional"),
    ("AfDB Procurement", "https://www.afdb.org/en/projects-and-operations/procurement", "africa_regional"),
    ("African Union Commission", "https://au.int/en/procurement", "africa_regional"),
    ("East African Development Bank", "https://www.eadb.org/procurement/", "africa_regional"),
    ("StatBank Africa Tenders", "https://www.statbankafrica.com/", "africa_regional"),
    
    # ========== UNITED NATIONS GLOBAL ==========
    ("UNDP Procurement Notices", "https://procurement-notices.undp.org/", "global_multilateral"),
    ("UN Global Marketplace", "https://www.ungm.org/Public/Notice", "global_multilateral"),
    ("UNOPS Opportunities", "https://www.unops.org/business-opportunities", "global_multilateral"),
    ("UN Habitat Tenders", "https://unhabitat.org/procurement", "global_multilateral"),
    ("UNIDO Procurement", "https://www.unido.org/who-we-are/partnerships/business-cooperation/procurement", "global_multilateral"),
    ("UNESCO Procurement", "https://en.unesco.org/open-calls", "global_multilateral"),
    ("UNAIDS Procurement", "https://www.unaids.org/en/business-opportunities", "global_multilateral"),
    ("UNHCR Procurement", "https://www.unhcr.org/careers-and-business-opportunities/", "global_multilateral"),
    ("ILO Procurement", "https://www.ilo.org/global/about-the-ilo/work-for-the-ilo/business-opportunities/lang--en/index.htm", "global_multilateral"),
    
    # ========== WORLD BANK & DEVELOPMENT BANKS ==========
    ("World Bank Procurement", "https://projects.worldbank.org/en/projects-operations/procurement", "global_multilateral"),
    ("World Bank Contracts", "https://www.worldbank.org/en/about/business/contracts-and-procurement", "global_multilateral"),
    ("DevBusiness (World Bank)", "https://devbusiness.un.org/", "global_multilateral"),
    ("IDB Procurement Projects", "https://www.iadb.org/en/how-we-can-work-together/procurement/procurement-projects", "global_multilateral"),
    ("AIIB Project Procurement", "https://www.aiib.org/en/opportunities/business/project-procurement/index.html", "global_multilateral"),
    ("AsDB Procurement", "https://www.adb.org/who-we-are/headquarters/adb-business-opportunities", "global_multilateral"),
    ("EIB Procurement Calls", "https://www.eib.org/en/about/procurement/all/index.htm", "global_multilateral"),
    ("EBRD Procurement", "https://www.ebrd.com/work-with-us/procurement.html", "global_multilateral"),
    ("New Development Bank", "https://www.ndb.int/procurement/", "global_multilateral"),
    
    # ========== WHO & HEALTH SECTOR ==========
    ("WHO Procurement", "https://www.who.int/about/accountability/procurement", "global_multilateral"),
    ("WFP Procurement", "https://www.wfp.org/procurement", "global_multilateral"),
    ("GAVI Procurement", "https://www.gavi.org/our-work/procurement", "global_multilateral"),
    ("IFAD Procurement", "https://www.ifad.org/en/business-opportunities", "global_multilateral"),
    ("FAO Procurement", "https://www.fao.org/about/business-opportunities/en", "global_multilateral"),
    
    # ========== EUROPE - PUBLIC PROCUREMENT ==========
    ("TED Europa Tenders", "https://ted.europa.eu/en/search/result", "global_public"),
    ("UK Find a Tender", "https://www.find-tender.service.gov.uk/Search", "global_public"),
    ("Denmark Udbud", "https://udbud.dk/", "global_public"),
    ("Germany BUND", "https://www.service.bund.de/Content/DE/Ausschreibungen/Suche/Formular.html", "global_public"),
    ("EU Funding & Tenders", "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-search", "global_public"),
    ("France Marches Publics", "https://www.marches.senat.fr/", "global_public"),
    ("Spain Licitaciones", "https://www.placespublicas.com/", "global_public"),
    
    # ========== AMERICAS & PACIFIC ==========
    ("SAM.gov (US Federal)", "https://sam.gov/search/?index=opp&page=1&sort=-modifiedDate", "global_public"),
    ("Australia AusTender", "https://www.tenders.gov.au/", "global_public"),
    ("Canada Buy & Sell", "https://www.buyandsell.gc.ca/", "global_public"),
    
    # ========== ASIA-PACIFIC ==========
    ("India CPPP", "https://eprocure.gov.in/eprocure/app", "global_public"),
    ("Singapore GeBIZ", "https://www.gebiz.gov.sg/", "global_public"),
    ("Malaysia eProcurement", "https://www.eproc.gov.my/semakan/", "global_public"),
    ("Philippines PhilGEPS", "https://www.philgeps.gov.ph/", "global_public"),
    ("Vietnam Procurement", "https://muasamcong.mpi.gov.vn/", "global_public"),
    ("Indonesia LPSE", "https://portal.lpse.go.id/app/", "global_public"),
    ("Thailand eProcurement", "https://www.procure.go.th/", "global_public"),
    
    # ========== COMMONWEALTH & MULTILATERAL ==========
    ("Commonwealth Secretariat Procurement", "https://thecommonwealth.org/procurement", "global_multilateral"),
    ("WIPO Procurement", "https://www.wipo.int/about-wipo/en/business-opportunities/procurement/", "global_multilateral"),
    ("WTO Procurement", "https://www.wto.org/english/tratop_e/invtrans_e/inv_10_e.htm", "global_multilateral"),
    ("GEF Procurement", "https://www.thegef.org/business-opportunities", "global_multilateral"),
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
                TenderSource(  # type: ignore[call-arg]
                    name=name,  # type: ignore[arg-type]
                    url=url,  # type: ignore[arg-type]
                    active=True,  # type: ignore[arg-type]
                    favorite=False,  # type: ignore[arg-type]
                    source_group=source_group,  # type: ignore[arg-type]
                    source_tags=json.dumps([source_group]),  # type: ignore[arg-type]
                )
            )

        db.session.commit()
        print(f"Added {len(DEFAULT_SOURCES)} tender sources")


if __name__ == "__main__":
    init_sources()
