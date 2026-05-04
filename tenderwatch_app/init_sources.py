"""
TenderWatch Kenya - Initialization Script
Seeds Kenya government tender sources plus key multilateral donors active in Kenya.
"""

import json

from app import create_app  # type: ignore[attr-defined]
from app.extensions import db  # type: ignore[attr-defined]
from app.models import TenderSource  # type: ignore[attr-defined]


DEFAULT_SOURCES = [
    # ========== KENYA - NATIONAL GOVERNMENT ==========
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

    # ========== KENYA - COUNTY GOVERNMENTS ==========
    ("Nairobi City County", "https://nairobi.go.ke/tenders/", "africa_priority"),
    ("Mombasa County", "https://www.mombasa.go.ke/tenders/", "africa_priority"),
    ("Kisumu County", "https://kisumu.go.ke/tenders/", "africa_priority"),
    ("Nakuru County", "https://nakuru.go.ke/tenders/", "africa_priority"),
    ("Kiambu County", "https://www.kiambu.go.ke/tenders/", "africa_priority"),
    ("Machakos County", "https://machakos.go.ke/tenders/", "africa_priority"),
    ("Uasin Gishu County", "https://uasingishu.go.ke/tenders/", "africa_priority"),

    # ========== KENYA - STATE CORPORATIONS & PARASTATALS ==========
    ("Kenya Power Tenders", "https://www.kplc.co.ke/content/item/1/tenders", "africa_priority"),
    ("KENHA Tenders", "https://www.kenha.co.ke/index.php/procurement/tenders", "africa_priority"),
    ("KURA Tenders", "https://www.kura.go.ke/procurement/", "africa_priority"),
    ("Kenya Pipeline Company", "https://www.kpc.co.ke/tenders/", "africa_priority"),
    ("Kenyatta National Hospital", "https://www.knh.or.ke/index.php/procurement", "africa_priority"),
    ("NHIF Tenders", "https://www.nhif.or.ke/procurement/", "africa_priority"),
    ("NSSF Tenders", "https://www.nssf.or.ke/procurement/", "africa_priority"),
    ("Kenya Airports Authority", "https://www.kaa.go.ke/business-opportunities/procurement/", "africa_priority"),
    ("Kenya Civil Aviation Authority", "https://www.kcaa.or.ke/procurement", "africa_priority"),

    # ========== KENYA - UNIVERSITIES & RESEARCH ==========
    ("University of Nairobi", "https://www.uonbi.ac.ke/tenders", "africa_priority"),
    ("Kenyatta University", "https://www.ku.ac.ke/tenders/", "africa_priority"),
    ("JKUAT Tenders", "https://www.jkuat.ac.ke/tenders/", "africa_priority"),
    ("Moi University Tenders", "https://www.mu.ac.ke/index.php/tenders", "africa_priority"),
    ("Kenya Medical Research Institute", "https://www.kemri.go.ke/index.php/tenders", "africa_priority"),

    # ========== MULTILATERAL DONORS ACTIVE IN KENYA ==========
    ("UNDP Procurement Notices", "https://procurement-notices.undp.org/", "global_multilateral"),
    ("UN Global Marketplace", "https://www.ungm.org/Public/Notice", "global_multilateral"),
    ("UNOPS Opportunities", "https://www.unops.org/business-opportunities", "global_multilateral"),
    ("UN Habitat Tenders", "https://unhabitat.org/procurement", "global_multilateral"),
    ("World Bank Procurement", "https://projects.worldbank.org/en/projects-operations/procurement", "global_multilateral"),
    ("AfDB Procurement", "https://www.afdb.org/en/projects-and-operations/procurement", "global_multilateral"),
    ("TradeMark Africa Procurement", "https://trademarkafrica.com/procurement/", "global_multilateral"),
    ("East African Development Bank", "https://www.eadb.org/procurement/", "global_multilateral"),
    ("WHO Kenya", "https://www.who.int/about/accountability/procurement", "global_multilateral"),
    ("WFP Procurement", "https://www.wfp.org/procurement", "global_multilateral"),
    ("FAO Procurement", "https://www.fao.org/about/business-opportunities/en", "global_multilateral"),
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
