"""
TenderWatch - Streamlit Version
Simple, powerful tender scanning for cBrain F2 Platform
"""

import json
import importlib
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

# Ensure project root is on sys.path and avoid module name collisions.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if "app" in sys.modules and not hasattr(sys.modules["app"], "__path__"):
    del sys.modules["app"]
importlib.invalidate_caches()

# Initialize database
from app import create_app
from app.extensions import db
from app.models import TenderSource, TenderResult, AppSettings
from app.scraper import run_scan
from app.scoring import score_text
from app.categorizer import categorize

# Set page config
st.set_page_config(
    page_title="TenderWatch - cBrain",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# PWA Installation Support - inject manifest and service worker
st.markdown("""
<link rel="manifest" href="/static/manifest.json">
<link rel="apple-touch-icon" href="/static/icons/apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="192x192" href="/static/icons/icon-192.png">
<link rel="icon" type="image/png" sizes="32x32" href="/static/icons/icon-32.png">
<meta name="theme-color" content="#2563eb">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="TenderWatch">
<meta name="mobile-web-app-capable" content="yes">
<meta name="application-name" content="TenderWatch">
<meta name="msapplication-TileColor" content="#2563eb">
<meta name="msapplication-TileImage" content="/static/icons/icon-144.png">
<script src="/static/pwa.js" defer></script>
""", unsafe_allow_html=True)

# Initialize session state for theme
if 'theme' not in st.session_state:
    st.session_state.theme = 'light'

# Custom CSS for modern, friendly design with dark mode
st.markdown(f"""
<style>
    /* Theme Variables */
    :root {{
        --bg-primary: {'#0f172a' if st.session_state.theme == 'dark' else '#ffffff'};
        --bg-secondary: {'#0a0a0a' if st.session_state.theme == 'dark' else '#fafafa'};
        --text-primary: {'#ffffff' if st.session_state.theme == 'dark' else '#000000'};
        --text-secondary: {'#a3a3a3' if st.session_state.theme == 'dark' else '#737373'};
        --border-color: {'#262626' if st.session_state.theme == 'dark' else '#e5e5e5'};
        --card-bg: {'#0a0a0a' if st.session_state.theme == 'dark' else '#ffffff'};
    }}
    
    /* Main background */
    .main {{
        background: {'linear-gradient(135deg, #000000 0%, #0a0a0a 100%)' if st.session_state.theme == 'dark' else '#ffffff'};
        background-attachment: fixed;
    }}
    
    .stApp {{
        background: transparent;
    }}
    
    /* Modern card styling */
    [data-testid="stMetricValue"] {{
        font-size: 2rem;
        font-weight: 700;
        color: var(--text-primary);
    }}
    
    [data-testid="stMetricLabel"] {{
        color: var(--text-secondary);
        font-weight: 600;
    }}
    
    /* Button styling */
    .stButton>button {{
        background: linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%);
        color: white;
        border-radius: 25px;
        padding: 0.75rem 2rem;
        font-weight: 700;
        border: none;
        box-shadow: 0 4px 12px rgba(139, 92, 246, 0.4);
        transition: all 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55);
    }}
    
    .stButton>button:hover {{
        transform: translateY(-4px) scale(1.05);
        box-shadow: 0 12px 24px rgba(236, 72, 153, 0.5);
    }}
    
    /* Headers */
    h1, h2, h3 {{
        color: var(--text-primary);
        font-weight: 700;
    }}
    
    /* Score badges */
    .high-score {{
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 10px;
        font-weight: 700;
        display: inline-block;
        font-size: 1.2rem;
    }}
    .medium-score {{
        background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 10px;
        font-weight: 700;
        display: inline-block;
        font-size: 1.2rem;
    }}
    .low-score {{
        background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 10px;
        font-weight: 700;
        display: inline-block;
        font-size: 1.2rem;
    }}
    
    /* Input styling */
    .stTextInput>div>div>input, .stSelectbox>div>div>select, .stNumberInput>div>div>input {{
        border-radius: 10px;
        border: 2px solid var(--border-color);
        background: var(--card-bg);
        color: var(--text-primary) !important;
    }}
    
    /* Card containers */
    .stExpander {{
        background: var(--card-bg);
        border-radius: 16px;
        border: 1px solid var(--border-color);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }}
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, {'#1e293b' if st.session_state.theme == 'dark' else '#2d3e50'} 0%, {'#0f172a' if st.session_state.theme == 'dark' else '#2ba8d8'} 100%);
    }}
    
    [data-testid="stSidebar"] * {{
        color: white !important;
    }}
    
    /* Metric cards */
    [data-testid="stMetric"] {{
        background: var(--card-bg);
        padding: 1.5rem;
        border-radius: 16px;
        border: 1px solid var(--border-color);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        transition: all 0.3s ease;
    }}
    
    [data-testid="stMetric"]:hover {{
        transform: translateY(-4px);
        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.1);
    }}
    
    /* Info/Success/Warning/Error boxes */
    .stAlert {{
        border-radius: 12px;
        border-left: 4px solid;
    }}
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
    }}
    
    .stTabs [data-baseweb="tab"] {{
        border-radius: 12px;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
    }}
    
    /* Dataframe styling */
    [data-testid="stDataFrame"] {{
        border-radius: 12px;
        overflow: hidden;
    }}
</style>
""", unsafe_allow_html=True)

# Initialize Flask app context for database
app = create_app(start_scheduler=False, init_db=True)

def init_db():
    """Initialize database with app context"""
    with app.app_context():
        # Define all default sources
        default_sources_data = [
            # UN System
            ("UNDP Procurement", "https://procurement-notices.undp.org/", True),
            ("UN Global Marketplace", "https://www.ungm.org/Public/Notice", True),
            ("UNICEF Supply", "https://www.unicef.org/supply/procurement-services", False),
            ("WHO Procurement", "https://www.who.int/about/accountability/procurement", False),
            ("WFP Procurement", "https://www.wfp.org/procurement", False),
            ("UNOPS Opportunities", "https://www.unops.org/business-opportunities", False),
            ("UNESCO Procurement", "https://en.unesco.org/procurement", False),
            ("FAO Procurement", "https://www.fao.org/unfao/procurement/", False),
            
            # Development Banks
            ("World Bank Procurement", "https://projects.worldbank.org/en/projects-operations/procurement", True),
            ("DevBusiness (World Bank)", "https://devbusiness.un.org/content/tenders", False),
            ("AfDB Procurement", "https://www.afdb.org/en/about-us/corporate-procurement/procurement-notices", False),
            ("ADB Procurement", "https://www.adb.org/projects/tenders/all", False),
            ("IDB Procurement", "https://www.iadb.org/en/procurement/current-opportunities", False),
            ("EBRD Procurement", "https://www.ebrd.com/work-with-us/procurement.html", False),
            ("EIB Procurement", "https://www.eib.org/en/about/procurement/index.htm", False),
            ("IsDB Procurement", "https://www.isdb.org/procurement", False),
            
            # European Union
            ("TED Europa", "https://ted.europa.eu/en/search/result", True),
            ("EU Funding Tenders", "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-search", False),
            
            # Government Portals - Europe
            ("UK Contracts Finder", "https://www.contractsfinder.service.gov.uk/Search/Results", False),
            ("UK Find a Tender", "https://www.find-tender.service.gov.uk/Search", False),
            ("Germany BUND", "https://www.service.bund.de/Content/DE/Ausschreibungen/", False),
            ("France BOAMP", "https://www.boamp.fr/pages/recherche/", False),
            ("Netherlands TenderNed", "https://www.tenderned.nl/tenderned-tap/aankondigingen", False),
            
            # Government Portals - Americas
            ("SAM.gov (US Federal)", "https://sam.gov/search/?index=opp&page=1&sort=-modifiedDate", True),
            ("Canada Buyandsell", "https://buyandsell.gc.ca/procurement-data/tenders", False),
            
            # Government Portals - Africa
            ("Kenya PPB", "https://tenders.go.ke/", True),
            ("South Africa eTender", "https://www.etenders.gov.za/", False),
            ("Nigeria BPP", "https://www.bpp.gov.ng/", False),
            ("Ghana PPA", "https://ppaghana.org/tenders.asp", False),
            ("Tanzania PPRA", "https://www.ppra.go.tz/", False),
            ("Uganda PPDA", "https://www.ppda.go.ug/", False),
            ("Rwanda RPPA", "https://umucyo.gov.rw/", False),
            ("Ethiopia PPA", "https://ppa.gov.et/", False),
            
            # Government Portals - Asia Pacific
            ("Australia AusTender", "https://www.tenders.gov.au/", False),
            ("New Zealand GETS", "https://www.gets.govt.nz/ExternalIndex.htm", False),
            ("India CPPP", "https://eprocure.gov.in/eprocure/app", False),
            ("Philippines PhilGEPS", "https://www.philgeps.gov.ph/", False),
            ("Singapore GeBIZ", "https://www.gebiz.gov.sg/", False),
            
            # International Organizations
            ("NATO Procurement", "https://www.nspa.nato.int/business", False),
            ("Commonwealth Secretariat", "https://thecommonwealth.org/procurement", False),
            
            # Development/NGO Portals
            ("DevEx Funding", "https://www.devex.com/funding", False),
            ("ReliefWeb Jobs", "https://reliefweb.int/jobs", False),
            
            # Tender Aggregators
            ("DgMarket", "https://www.dgmarket.com/", False),
            ("Global Tenders", "https://www.globaltenders.com/", False),
            
            # Kenya Government Sources
            ("Kenya PPIP", "https://tenders.go.ke/website/tenders/all", True),
            ("Kenya eTender", "https://supplier.treasury.go.ke/site/tenders.go/public", True),
            ("KRA Tenders", "https://www.kra.go.ke/en/helping-tax-payers/tenders", True),
            ("KURA Tenders", "https://www.kura.go.ke/tenders", True),
            ("KENHA Tenders", "https://www.kenha.co.ke/index.php/tenders", True),
            ("Kenya Power Tenders", "https://www.kplc.co.ke/category/view/47/tenders", True),
            ("NHIF Tenders", "https://www.nhif.or.ke/tenders/", True),
            ("NSSF Tenders", "https://www.nssf.or.ke/tenders", True),
            ("CBK Tenders", "https://www.centralbank.go.ke/tenders/", True),
            
            # Kenya Parastatals (Priority - ICT/EDRMS tenders)
            ("KAA Procurement", "https://www.kaa.go.ke/corporate/procurement/", True),  # Kenya Airports Authority - EDRMS, ICT
            ("Kenya Railways", "https://krc.co.ke/tenders/", True),
            ("KETRACO Tenders", "https://www.ketraco.co.ke/tenders/", True),  # Transmission company
            ("KenGen Tenders", "https://www.kengen.co.ke/index.php/procurement.html", True),
            ("KEBS Tenders", "https://www.kebs.org/index.php?option=com_content&view=article&id=190", False),
            ("NTSA Tenders", "https://www.ntsa.go.ke/tenders/", True),  # Transport authority
            ("KEMSA Tenders", "https://www.kemsa.co.ke/tenders/", True),  # Medical supplies
            ("KPA Tenders", "https://www.kpa.co.ke/Tenders/Pages/default.aspx", True),  # Kenya Ports Authority
            ("NEMA Tenders", "https://www.nema.go.ke/index.php/tenders", False),
            ("CAK Tenders", "https://cak.go.ke/tenders", False),  # Communications Authority
            ("ICT Authority", "https://icta.go.ke/tenders/", True),  # ICT Authority - high priority
            
            # Kenya Counties
            ("Nairobi County Tenders", "https://nairobi.go.ke/tenders/", True),
            ("Mombasa County Tenders", "https://www.mombasa.go.ke/tenders/", False),
            ("Kisumu County Tenders", "https://kisumu.go.ke/tenders/", False),
            ("Nakuru County Tenders", "https://nakuru.go.ke/tenders/", False),
            ("Kiambu County Tenders", "https://kiambu.go.ke/tenders/", False),
            
            # Kenya Universities
            ("UoN Procurement", "https://www.uonbi.ac.ke/content/procurement", False),
            ("KU Tenders", "https://www.ku.ac.ke/schools/tenders", False),
            ("JKUAT Tenders", "https://www.jkuat.ac.ke/tenders/", False),
            
            # Kenya Hospitals
            ("KNH Tenders", "https://knh.or.ke/tenders/", False),
            
            # Kenya Aggregators
            ("MyGov Kenya", "https://www.mygov.go.ke/?s=tender", True),
            ("Tendersinfo Kenya", "https://www.tendersinfo.com/global-kenya-tenders.php", False),
        ]
        
        # Add missing sources (check by URL to avoid duplicates)
        existing_urls = {s.url for s in TenderSource.query.all()}
        added_count = 0
        for name, url, is_favorite in default_sources_data:
            if url not in existing_urls:
                source = TenderSource(name=name, url=url, active=True, favorite=is_favorite)
                db.session.add(source)
                added_count += 1
        
        if added_count > 0:
            db.session.commit()
            print(f"✅ Added {added_count} new tender sources")
        
        # Translate any untranslated tenders
        translate_untranslated_tenders()

def translate_untranslated_tenders():
    """Translate tenders that don't have translations yet"""
    from app.translator import translate_to_english, detect_language
    
    with app.app_context():
        # Find tenders where title_translated is empty or same as title
        untranslated = TenderResult.query.filter(
            (TenderResult.title_translated == None) | 
            (TenderResult.title_translated == "") |
            (TenderResult.title_translated == TenderResult.title)
        ).limit(20).all()  # Limit to 20 at a time to avoid timeout
        
        if untranslated:
            print(f"🌐 Translating {len(untranslated)} untranslated tenders...")
            translated_count = 0
            
            for tender in untranslated:
                # Check if title is non-English
                detected_lang = detect_language(tender.title)
                if detected_lang != "en":
                    translated_title = translate_to_english(tender.title)
                    if translated_title and translated_title.lower() != tender.title.lower():
                        tender.title_translated = translated_title
                        translated_count += 1
                        print(f"  ✅ Translated: {tender.title[:40]}...")
                else:
                    # Mark English tenders as translated (same as original)
                    tender.title_translated = tender.title
            
            if translated_count > 0:
                db.session.commit()
                print(f"✅ Translated {translated_count} tenders")

def get_tenders(filters=None):
    """Get tenders with optional filters - only from last month"""
    with app.app_context():
        # Filter tenders from last month only
        one_month_ago = datetime.utcnow() - timedelta(days=30)
        query = TenderResult.query.filter(TenderResult.created_at >= one_month_ago)
        
        if filters:
            if filters.get('min_score'):
                query = query.filter(TenderResult.score >= filters['min_score'])
            if filters.get('category') and filters['category'] != "All":
                query = query.filter(TenderResult.category == filters['category'])
            if filters.get('search'):
                search_term = f"%{filters['search']}%"
                query = query.filter(
                    TenderResult.title.ilike(search_term) | 
                    TenderResult.title_translated.ilike(search_term) |
                    TenderResult.description.ilike(search_term) |
                    TenderResult.description_translated.ilike(search_term)
                )
            if filters.get('favorites_only'):
                query = query.filter(TenderResult.favorite == True)
            if filters.get('saved_only'):
                query = query.filter(TenderResult.saved == True)
            
            # New filters: Priority, Status, Country, F2 Fit
            if filters.get('priority') and filters['priority'] != "All":
                query = query.filter(TenderResult.priority_level == filters['priority'])
            if filters.get('status') and filters['status'] != "All":
                query = query.filter(TenderResult.procurement_status == filters['status'])
            if filters.get('country') and filters['country'] != "All":
                query = query.filter(TenderResult.country == filters['country'])
            if filters.get('f2_fit') and filters['f2_fit'] != "All":
                query = query.filter(TenderResult.likely_fit_for_f2 == filters['f2_fit'])
        
        # Sort
        sort_by = filters.get('sort_by', 'score') if filters else 'score'
        if sort_by == 'score':
            query = query.order_by(TenderResult.score.desc())
        elif sort_by == 'date':
            query = query.order_by(TenderResult.created_at.desc())
        elif sort_by == 'deadline':
            query = query.order_by(TenderResult.deadline.asc())
        
        return query.all()

def get_sources():
    """Get all tender sources"""
    with app.app_context():
        return TenderSource.query.all()

def get_stats():
    """Get dashboard statistics - only from last month"""
    with app.app_context():
        one_month_ago = datetime.utcnow() - timedelta(days=30)
        
        total = TenderResult.query.filter(TenderResult.created_at >= one_month_ago).count()
        high_score = TenderResult.query.filter(
            TenderResult.score >= 70,
            TenderResult.created_at >= one_month_ago
        ).count()
        saved = TenderResult.query.filter_by(saved=True).filter(
            TenderResult.created_at >= one_month_ago
        ).count()
        favorites = TenderResult.query.filter_by(favorite=True).filter(
            TenderResult.created_at >= one_month_ago
        ).count()
        active_sources = TenderSource.query.filter_by(active=True).count()
        
        # Get categories (last month only)
        categories = db.session.query(
            TenderResult.category,
            db.func.count(TenderResult.id).label('count')
        ).filter(TenderResult.created_at >= one_month_ago).group_by(TenderResult.category).all()
        
        return {
            'total': total,
            'high_score': high_score,
            'saved': saved,
            'favorites': favorites,
            'active_sources': active_sources,
            'categories': dict(categories) if categories else {}
        }

def toggle_favorite(tender_id):
    """Toggle favorite status"""
    with app.app_context():
        tender = TenderResult.query.get(tender_id)
        if tender:
            tender.favorite = not tender.favorite
            db.session.commit()
            return True
    return False

def toggle_saved(tender_id):
    """Toggle saved status"""
    with app.app_context():
        tender = TenderResult.query.get(tender_id)
        if tender:
            tender.saved = not tender.saved
            db.session.commit()
            return True
    return False

def toggle_source(source_id):
    """Toggle source active status"""
    with app.app_context():
        source = TenderSource.query.get(source_id)
        if source:
            source.active = not source.active
            db.session.commit()
            return True
    return False

def add_source(name, url):
    """Add new tender source"""
    with app.app_context():
        source = TenderSource(name=name, url=url, active=True)
        db.session.add(source)
        db.session.commit()
        return True

def delete_source(source_id):
    """Delete tender source"""
    with app.app_context():
        source = TenderSource.query.get(source_id)
        if source:
            db.session.delete(source)
            db.session.commit()
            return True
    return False

def run_tender_scan():
    """Run tender scan"""
    with app.app_context():
        new_tenders = run_scan(flask_app=app)
    print(f"[DEBUG] run_tender_scan: Found {len(new_tenders)} new tenders.")
    return new_tenders

# Initialize database
init_db()

# Sidebar
with st.sidebar:
    st.title("🎯 TenderWatch")
    st.markdown("**cBrain F2 Tenderwatch**")
    st.markdown("---")
    
    page = st.radio(
        "Navigation",
        ["📊 Dashboard", "🔍 Scan & Results", "📁 Sources", "⭐ Favorites", "💾 Saved", "⚙️ Settings"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    # Subtle theme toggle at bottom
    if st.button("◐", key="theme_toggle", help="Toggle theme"):
        st.session_state.theme = 'dark' if st.session_state.theme == 'light' else 'light'
        st.rerun()
    
    st.caption("© 2026 cBrain TenderWatch")

# Main content based on selected page
if page == "📊 Dashboard":
    st.title("🎉 Your Opportunity Hub!")
    st.markdown("Let's find some amazing tenders today! ✨")
    
    stats = get_stats()
    
    # Metrics row with icons
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown("""
            <div style='text-align: center; padding: 1rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 16px; box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);'>
                <div style='font-size: 2.5rem; margin-bottom: 0.5rem;'>📊</div>
                <div style='font-size: 2rem; font-weight: 700; color: white;'>""" + str(stats['total']) + """</div>
                <div style='font-size: 0.9rem; color: rgba(255, 255, 255, 0.9);'>Total Tenders</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
            <div style='text-align: center; padding: 1rem; background: linear-gradient(135deg, #10b981 0%, #059669 100%); border-radius: 16px; box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);'>
                <div style='font-size: 2.5rem; margin-bottom: 0.5rem;'>🎯</div>
                <div style='font-size: 2rem; font-weight: 700; color: white;'>""" + str(stats['high_score']) + """</div>
                <div style='font-size: 0.9rem; color: rgba(255, 255, 255, 0.9);'>High Score (≥70%)</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
            <div style='text-align: center; padding: 1rem; background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); border-radius: 16px; box-shadow: 0 4px 12px rgba(245, 158, 11, 0.3);'>
                <div style='font-size: 2.5rem; margin-bottom: 0.5rem;'>💾</div>
                <div style='font-size: 2rem; font-weight: 700; color: white;'>""" + str(stats['saved']) + """</div>
                <div style='font-size: 0.9rem; color: rgba(255, 255, 255, 0.9);'>Saved</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
            <div style='text-align: center; padding: 1rem; background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); border-radius: 16px; box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3);'>
                <div style='font-size: 2.5rem; margin-bottom: 0.5rem;'>⭐</div>
                <div style='font-size: 2rem; font-weight: 700; color: white;'>""" + str(stats['favorites']) + """</div>
                <div style='font-size: 0.9rem; color: rgba(255, 255, 255, 0.9);'>Favorites</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.markdown("""
            <div style='text-align: center; padding: 1rem; background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%); border-radius: 16px; box-shadow: 0 4px 12px rgba(6, 182, 212, 0.3);'>
                <div style='font-size: 2.5rem; margin-bottom: 0.5rem;'>📡</div>
                <div style='font-size: 2rem; font-weight: 700; color: white;'>""" + str(stats['active_sources']) + """</div>
                <div style='font-size: 0.9rem; color: rgba(255, 255, 255, 0.9);'>Active Sources</div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Category breakdown
    if stats['categories']:
        st.subheader("📋 Tenders by Category")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Bar chart
            cat_df = pd.DataFrame(
                list(stats['categories'].items()),
                columns=['Category', 'Count']
            ).sort_values('Count', ascending=False)
            st.bar_chart(cat_df.set_index('Category'), height=400)
        
        with col2:
            # Table
            st.dataframe(
                cat_df,
                hide_index=True,
                use_container_width=True
            )
    
    # Recent tenders
    st.markdown("---")
    st.subheader("🕒 Recent Tenders (Top 10)")
    
    recent = get_tenders({'sort_by': 'date'})[:10]
    
    if recent:
        for tender in recent:
            score_class = "high-score" if tender.score >= 70 else "medium-score" if tender.score >= 40 else "low-score"
            
            with st.container():
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.markdown(f"**{tender.title}**")
                    st.caption(f"{tender.category} • {tender.created_at.strftime('%Y-%m-%d %H:%M')}")
                
                with col2:
                    st.markdown(f"<span class='{score_class}'>{tender.score:.1f}%</span>", unsafe_allow_html=True)
                
                with col3:
                    st.link_button("View →", tender.link, use_container_width=True)
                
                st.markdown("---")
    else:
        st.markdown("""
        <div style='text-align: center; padding: 3rem; background: linear-gradient(135deg, #fef3c7 0%, #fff 100%); 
                    border-radius: 30px; margin: 2rem 0; box-shadow: 0 8px 24px rgba(139, 92, 246, 0.2);'>
            <div style='font-size: 4rem; margin-bottom: 1rem; animation: bounce 2s infinite;'>🌟</div>
            <h3 style='color: #8b5cf6; margin-bottom: 1rem; font-weight: 700;'>Ready to Get Started?</h3>
            <p style='color: #6b7280; font-size: 1.1rem;'>
                Let's find some amazing opportunities! Click the button in the sidebar 👈
            </p>
        </div>
        <style>
        @keyframes bounce {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-20px); }
        }
        </style>
        """, unsafe_allow_html=True)
        st.info("""**Get started:**
1. Click **🔍 Scan & Results** in the sidebar
2. Click **🚀 Let's Go!** to find tenders
3. Or add tender sources in **📁 Sources**
        """)

elif page == "🔍 Scan & Results":
    st.title("🎯 Find Your Perfect Match!")
    
    # Check if a tender is selected for detail view
    if 'selected_tender' in st.session_state and st.session_state['selected_tender']:
        tender_id = st.session_state['selected_tender']
        with app.app_context():
            tender = TenderResult.query.get(tender_id)
            if tender:
                # Back button
                if st.button("← Back to Results", key="back_from_detail"):
                    st.session_state['selected_tender'] = None
                    st.rerun()
                
                st.markdown("---")
                
                # Tender title with score (prefer translated if available)
                display_title = tender.title_translated if tender.title_translated and tender.title_translated != tender.title else tender.title
                score_color = "#10b981" if tender.score >= 70 else "#f59e0b" if tender.score >= 40 else "#ef4444"
                st.markdown(f"""
                <div style='padding: 1.5rem; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-radius: 16px; margin-bottom: 1rem;'>
                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                        <h2 style='color: white; margin: 0; font-size: 1.5rem;'>{display_title}</h2>
                        <span style='background: {score_color}; color: white; padding: 8px 16px; border-radius: 20px; font-weight: 700; font-size: 1.2rem;'>{tender.score:.0f}%</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Details in columns
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("### 📋 Basic Information")
                    st.markdown(f"**Category:** {tender.category or 'Uncategorized'}")
                    st.markdown(f"**Country:** {tender.country or 'Not specified'}")
                    st.markdown(f"**Deadline:** {tender.deadline or 'Not specified'}")
                    st.markdown(f"**Found on:** {tender.created_at.strftime('%Y-%m-%d %H:%M') if tender.created_at else 'Unknown'}")
                    
                    st.markdown("### 🔗 Source")
                    st.link_button("🌐 View Original Tender", tender.link, use_container_width=True)
                
                with col2:
                    st.markdown("### 🎯 Scoring Details")
                    st.markdown(f"**Match Score:** {tender.score:.1f}%")
                    st.markdown(f"**Confidence:** {(tender.confidence or 0) * 100:.0f}%")
                    
                    if tender.keywords_matched:
                        st.markdown("**Matched Keywords:**")
                        keywords = tender.keywords_matched.split(", ") if tender.keywords_matched else []
                        for kw in keywords[:10]:
                            st.markdown(f"• {kw}")
                        if len(keywords) > 10:
                            st.markdown(f"*...and {len(keywords) - 10} more*")
                
                st.markdown("---")
                
                # Description (prefer translated if available)
                st.markdown("### 📝 Description")
                display_description = tender.description_translated if tender.description_translated and tender.description_translated != tender.description else tender.description
                st.markdown(display_description or "No description available.")
                
                # Show original language notice if translated
                if tender.title_translated and tender.title_translated != tender.title:
                    st.markdown("---")
                    st.markdown("### 🌐 Original Language")
                    with st.expander("View Original (Non-English)"):
                        st.markdown(f"**Original Title:** {tender.title}")
                        if tender.description and tender.description != tender.description_translated:
                            st.markdown(f"**Original Description:** {tender.description}")
                
                # Scoring breakdown
                if tender.scoring_breakdown:
                    st.markdown("### 📊 Scoring Breakdown")
                    try:
                        import json
                        breakdown = json.loads(tender.scoring_breakdown) if isinstance(tender.scoring_breakdown, str) else tender.scoring_breakdown
                        
                        if isinstance(breakdown, dict):
                            if 'unique_keywords' in breakdown:
                                st.markdown(f"**Keywords Found:** {breakdown.get('keywords_found', 0)} / {breakdown.get('total_keywords_in_system', 'N/A')}")
                            if 'matched_groups' in breakdown:
                                st.markdown("**Matched Categories:**")
                                for group in breakdown.get('matched_groups', []):
                                    st.markdown(f"• **{group.get('group', 'Unknown')}**: {group.get('count', 0)} keywords")
                    except:
                        st.code(tender.scoring_breakdown)
                
                st.markdown("---")
                
                # Action buttons
                col1, col2, col3 = st.columns(3)
                with col1:
                    fav_label = "💛 Unfavorite" if tender.favorite else "⭐ Favorite"
                    if st.button(fav_label, key="detail_fav", use_container_width=True):
                        toggle_favorite(tender.id)
                        st.rerun()
                with col2:
                    save_label = "📤 Unsave" if tender.saved else "💾 Save"
                    if st.button(save_label, key="detail_save", use_container_width=True):
                        toggle_saved(tender.id)
                        st.rerun()
                with col3:
                    if st.button("← Back to Results", key="detail_back", use_container_width=True):
                        st.session_state['selected_tender'] = None
                        st.rerun()
            else:
                st.error("Tender not found")
                st.session_state['selected_tender'] = None
    else:
        # Normal scan & results view
        col1, col2 = st.columns([3, 1])
    
        with col1:
            st.markdown("✨ Let's discover some amazing opportunities together!")
    
        with col2:
            if st.button("🚀 Let's Go!", key="top_scan_button", type="primary", use_container_width=True):
                # Fun loading messages that rotate every few seconds
                cooking_messages = [
                    ("🍳", "Something delicious is cooking..."),
                    ("👨‍🍳", "Our tender chefs are hard at work!"),
                    ("🔥", "Heating up the search engines..."),
                    ("🌍", "Scanning the globe for opportunities..."),
                    ("☕", "Good things take time... grab a coffee!"),
                    ("🎣", "Fishing for the best tenders..."),
                    ("🔮", "Consulting the procurement crystal ball..."),
                    ("🚀", "Launching tender discovery rockets..."),
                    ("🎯", "Zeroing in on perfect matches..."),
                    ("⏳", "Sorry for the wait - quality hunting takes time!"),
                    ("🌟", "Polishing up some gems for you..."),
                    ("🔍", "Deep diving into tender databases..."),
                    ("🎪", "The tender circus is in town!"),
                    ("🍜", "Slow-cooking the best results..."),
                    ("🎸", "Jamming through procurement portals..."),
                    ("🏃", "Running through global tender sites..."),
                    ("📡", "Receiving transmissions from tender satellites..."),
                    ("🧙", "Wizarding up some opportunities..."),
                    ("🎁", "Unwrapping tender surprises..."),
                    ("🌈", "Following the tender rainbow..."),
                ]
                
                with st.spinner("Scanning sources..."):
                    new_tenders = run_tender_scan()
                if new_tenders:
                    st.success(f"🎉 Woohoo! Found {len(new_tenders)} awesome opportunities!")
                    st.balloons()
                else:
                    st.info("🤔 Hmm, nothing new right now. Check back soon!")
                st.rerun()
    
        st.markdown("---")
    
        # Filters and Export
        col_filter, col_export = st.columns([4, 1])
    
        with col_filter:
            st.subheader("🎛️ Filters")
    
        with col_export:
            # CSV Export button
            all_tenders_for_export = get_tenders()
            if all_tenders_for_export:
                csv_data = "Title,Link,Score,Category,Country,Deadline,Priority,Status,F2_Fit\n"
                for t in all_tenders_for_export:
                    csv_data += f'"{t.title}","{t.link}",{t.score},"{t.category or ""}","{t.country or ""}","{t.deadline or ""}","{t.priority_level or ""}","{t.procurement_status or ""}","{t.likely_fit_for_f2 or ""}"\n'
            
                st.download_button(
                    label="📥 Export CSV",
                    data=csv_data,
                    file_name=f"tenders_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    help="Download all tenders as CSV"
                )
    
        # Row 1: Score, Category, Sort, Search
        col1, col2, col3, col4 = st.columns(4)
    
        with col1:
            min_score = st.slider("Minimum Score", 0, 100, 0, 5)
    
        with col2:
            all_tenders = get_tenders()
            categories = ["All"] + sorted(list(set([t.category for t in all_tenders if t.category]))) if all_tenders else ["All"]
            category = st.selectbox("Category", categories)
    
        with col3:
            sort_by = st.selectbox("Sort By", ["score", "date", "deadline"])
    
        with col4:
            search = st.text_input("🔍 Search", placeholder="Search titles...", help="Search in tender titles")
        
        # Row 2: Priority, Status, Country, F2 Fit
        col5, col6, col7, col8 = st.columns(4)
        
        with col5:
            priority_options = ["All", "HIGH", "MEDIUM", "LOW", "STRATEGIC", "CONDITIONAL", "LOCKED"]
            priority_filter = st.selectbox("Priority", priority_options, help="Filter by F2 priority level")
        
        with col6:
            status_options = ["All", "open", "locked", "locked_but_open", "conditional_nogo", "conditional_strategic", "conditional_discuss"]
            status_filter = st.selectbox("Procurement Status", status_options, help="Filter by platform lock-in status")
        
        with col7:
            countries = ["All"] + sorted(list(set([t.country for t in all_tenders if t.country and t.country != "Unknown"]))) if all_tenders else ["All"]
            country_filter = st.selectbox("Country", countries, help="Filter by country")
        
        with col8:
            f2_fit_options = ["All", "true", "strategic", "discuss", "uncertain", "conditional", "no-go"]
            f2_fit_filter = st.selectbox("F2 Fit", f2_fit_options, help="Filter by F2 fit likelihood")

        # Get filtered tenders
        filters = {
            'min_score': min_score,
            'category': category,
            'sort_by': sort_by,
            'search': search,
            'priority': priority_filter,
            'status': status_filter,
            'country': country_filter,
            'f2_fit': f2_fit_filter,
        }
    
        tenders = get_tenders(filters)
    
        st.markdown(f"**{len(tenders)} tenders found**")
        st.markdown("---")
    
        # Display tenders
        if tenders:
            for tender in tenders:
                # Determine score styling
                if tender.score >= 70:
                    score_emoji = "🎯"
                    score_color = "#10b981"
                elif tender.score >= 40:
                    score_emoji = "📊"
                    score_color = "#f59e0b"
                else:
                    score_emoji = "📝"
                    score_color = "#ef4444"
            
                # Clean simple card layout
                with st.container():
                    # Header row (prefer translated title if available)
                    display_title = tender.title_translated if tender.title_translated and tender.title_translated != tender.title else tender.title
                    is_translated = tender.title_translated and tender.title_translated != tender.title
                    col_title, col_score = st.columns([5, 1])
                    with col_title:
                        title_suffix = " 🌐" if is_translated else ""  # Globe emoji for translated
                        st.markdown(f"### {display_title}{title_suffix}")
                    with col_score:
                        st.markdown(f"<span style='background: {score_color}; color: white; padding: 0.5rem 1rem; border-radius: 12px; font-weight: bold;'>{score_emoji} {tender.score:.0f}%</span>", unsafe_allow_html=True)
                
                    # Tags row
                    tags = []
                    if tender.category and tender.category != "Unclassified":
                        tags.append(f"📁 {tender.category}")
                    if tender.country:
                        tags.append(f"🌍 {tender.country}")
                    if tender.deadline:
                        tags.append(f"⏰ {tender.deadline}")
                
                    if tags:
                        st.markdown(" | ".join(tags))
                
                    # Action buttons
                    col1, col2, col3, col4 = st.columns(4)
                
                    with col1:
                        fav_label = "⭐ Favorited" if tender.favorite else "☆ Favorite"
                        if st.button(fav_label, key=f"fav_{tender.id}"):
                            toggle_favorite(tender.id)
                            st.rerun()
                
                    with col2:
                        save_label = "💾 Saved" if tender.saved else "📥 Save"
                        if st.button(save_label, key=f"save_{tender.id}"):
                            toggle_saved(tender.id)
                            st.rerun()
                
                    with col3:
                        st.link_button("🔗 View Source", tender.link)
                
                    with col4:
                        if st.button("📖 Details", key=f"detail_{tender.id}"):
                            st.session_state['selected_tender'] = tender.id
                            st.rerun()
                
                    st.markdown("---")
        else:
            st.markdown("""
            <style>
            @keyframes bounce {
                0%, 100% { transform: translateY(0); }
                50% { transform: translateY(-20px); }
            }
            </style>
            <div style='text-align: center; padding: 3rem 3rem 3rem 3rem; background: linear-gradient(135deg, #fef3c7 0%, #fff 100%); 
                        border-radius: 30px; margin: 2rem 0 2rem 0; box-shadow: 0 8px 24px rgba(139, 92, 246, 0.2); position: relative;'>
                <div style='font-size: 4rem; margin-bottom: 1rem; animation: bounce 2s infinite; cursor: pointer;'>🎯</div>
                <h3 style='color: #8b5cf6; margin-bottom: 1rem; font-weight: 700;'>Ready for the Hunt?</h3>
                <p style='color: #6b7280; font-size: 1.1rem; margin-bottom: 0.5rem;'>
                    Let's discover some amazing tenders together! 🚀
                </p>
                <p style='color: #a3a3a3; font-size: 0.85rem; margin-top: 0.5rem; font-style: italic;'>Click "Let's Go!" above to scan!</p>
            </div>
            """, unsafe_allow_html=True)

elif page == "📁 Sources":
    st.title("📁 Tender Sources")
    
    tab1, tab2 = st.tabs(["📋 Manage Sources", "➕ Add New Source"])
    
    with tab1:
        sources = get_sources()
        
        if sources:
            for source in sources:
                with st.container():
                    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                    
                    with col1:
                        status = "✅ Active" if source.active else "⏸️ Inactive"
                        fav = "⭐" if source.favorite else ""
                        st.markdown(f"**{source.name}** {status} {fav}")
                        st.caption(source.url)
                    
                    with col2:
                        toggle_label = "⏸️ Disable" if source.active else "✅ Enable"
                        if st.button(toggle_label, key=f"toggle_{source.id}", use_container_width=True):
                            toggle_source(source.id)
                            st.success(f"✅ Source {'disabled' if source.active else 'enabled'}!")
                            st.rerun()
                    
                    with col3:
                        st.link_button("Visit", source.url, use_container_width=True)
                    
                    with col4:
                        if st.button("🗑️ Delete", key=f"del_{source.id}"):
                            delete_source(source.id)
                            st.success("Source deleted!")
                            st.rerun()
                    
                    st.markdown("---")
        else:
            st.warning("⚠️ No sources configured yet!")
            st.info("💡 **Tip:** Switch to the 'Add New Source' tab to add your first tender source.")
    
    with tab2:
        st.markdown("### Add New Tender Source")
        
        with st.form("add_source_form"):
            name = st.text_input("Source Name", placeholder="e.g., UNDP Kenya")
            url = st.text_input("Source URL", placeholder="https://...")
            
            submitted = st.form_submit_button("➕ Add Source", type="primary")
            
            if submitted:
                if name and url:
                    if url.startswith('http://') or url.startswith('https://'):
                        add_source(name, url)
                        st.success(f"✅ Added source: {name}")
                        st.rerun()
                    else:
                        st.error("❌ URL must start with http:// or https://")
                else:
                    st.error("❌ Please provide both name and URL")

elif page == "⭐ Favorites":
    st.title("⭐ Favorite Tenders")
    
    filters = {'favorites_only': True, 'sort_by': 'score'}
    tenders = get_tenders(filters)
    
    st.markdown(f"**{len(tenders)} favorite tenders**")
    st.markdown("---")
    
    if tenders:
        for tender in tenders:
            score_color = "#10b981" if tender.score >= 70 else "#f59e0b" if tender.score >= 40 else "#ef4444"
            
            with st.expander(f"**[{tender.score:.1f}%]** {tender.title}"):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"**Category:** {tender.category}")
                    st.markdown(f"**Description:** {tender.description[:200]}...")
                    st.link_button("🔗 View Original", tender.link)
                
                with col2:
                    st.markdown(f"**Score:** <span style='color:{score_color};'>{tender.score:.1f}%</span>", unsafe_allow_html=True)
                    
                    if st.button("❌ Remove from Favorites", key=f"unfav_{tender.id}"):
                        toggle_favorite(tender.id)
                        st.rerun()
    else:
        st.info("No favorite tenders yet. Mark tenders as favorites from the Scan & Results page.")

elif page == "💾 Saved":
    st.title("💾 Saved Tenders")
    
    filters = {'saved_only': True, 'sort_by': 'score'}
    tenders = get_tenders(filters)
    
    st.markdown(f"**{len(tenders)} saved tenders**")
    st.markdown("---")
    
    if tenders:
        for tender in tenders:
            score_color = "#10b981" if tender.score >= 70 else "#f59e0b" if tender.score >= 40 else "#ef4444"
            
            with st.expander(f"**[{tender.score:.1f}%]** {tender.title}"):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"**Category:** {tender.category}")
                    st.markdown(f"**Description:** {tender.description[:200]}...")
                    st.link_button("🔗 View Original", tender.link)
                
                with col2:
                    st.markdown(f"**Score:** <span style='color:{score_color};'>{tender.score:.1f}%</span>", unsafe_allow_html=True)
                    
                    if st.button("❌ Remove from Saved", key=f"unsave_{tender.id}"):
                        toggle_saved(tender.id)
                        st.rerun()
    else:
        st.info("No saved tenders yet. Save tenders from the Scan & Results page for later review.")

elif page == "⚙️ Settings":
    st.title("⚙️ Settings")
    
    with app.app_context():
        settings = AppSettings.query.first()
        
        # Install App Section
        st.markdown("""
            <div style='padding: 1.5rem; background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%); border-radius: 16px; margin-bottom: 1.5rem;'>
                <div style='font-size: 2.5rem; text-align: center; margin-bottom: 0.5rem;'>📲</div>
                <div style='text-align: center; color: white; font-weight: 700; font-size: 1.4rem;'>Install TenderWatch</div>
                <div style='text-align: center; color: rgba(255,255,255,0.9); font-size: 0.9rem; margin-top: 0.5rem;'>Add to your home screen for quick access</div>
            </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            **📱 Mobile (Android/iOS):**
            1. Open this app in Chrome/Safari
            2. Tap the **Share** button (iOS) or **⋮ Menu** (Android)
            3. Select **"Add to Home Screen"**
            4. The app icon will appear on your home screen!
            """)
        
        with col2:
            st.markdown("""
            **💻 Desktop (Chrome/Edge):**
            1. Look for the **📲 Install** button in the address bar
            2. Or click the floating **📲** button (bottom-right)
            3. Click **"Install"** when prompted
            4. TenderWatch will open as a standalone app!
            """)
        
        st.markdown("---")
        
        # Daily Notifications Section
        st.markdown("""
            <div style='padding: 1.5rem; background: linear-gradient(135deg, #10b981 0%, #059669 100%); border-radius: 16px; margin-bottom: 1.5rem;'>
                <div style='font-size: 2.5rem; text-align: center; margin-bottom: 0.5rem;'>🔔</div>
                <div style='text-align: center; color: white; font-weight: 700; font-size: 1.4rem;'>Daily Scan Reminders</div>
                <div style='text-align: center; color: rgba(255,255,255,0.9); font-size: 0.9rem; margin-top: 0.5rem;'>Get notified to check for new tenders</div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        **How it works:**
        - Click the **🔔** button (bottom-right corner) to set up daily reminders
        - Choose your preferred time (e.g., 8:00 AM)
        - You'll receive a notification every day to scan for new tenders
        - Works on both mobile and desktop (after installing the app)
        
        **Tips:**
        - For best results, **install the app** first
        - Allow notifications when your browser asks
        - Notifications work even when the browser is closed (on supported devices)
        """)
        
        # JavaScript button for notification setup
        st.markdown("""
        <div style='text-align: center; margin: 1rem 0;'>
            <button onclick="window.TenderWatchPWA && window.TenderWatchPWA.setupNotifications()" 
                    style='background: linear-gradient(135deg, #10b981 0%, #059669 100%); 
                           color: white; 
                           border: none; 
                           padding: 12px 32px; 
                           border-radius: 8px; 
                           font-size: 1rem; 
                           font-weight: 600; 
                           cursor: pointer;
                           box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);'>
                🔔 Set Up Daily Notifications
            </button>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Notification Settings
        st.subheader("🔔 Notification Preferences")
        
        notification_enabled = st.checkbox("Enable In-App Notifications", 
                                          value=settings.notifications_enabled if settings and hasattr(settings, 'notifications_enabled') else False,
                                          help="Show notifications for high-score tenders during scans")
        
        min_score = st.slider("Minimum Score for Alerts", 0, 100, 
                             value=int(settings.min_score_to_notify) if settings else 70,
                             help="Only alert for tenders above this score")
        
        st.markdown("---")
        
        # Email Notification Settings
        st.subheader("📧 Email Notifications")
        
        email_enabled = st.checkbox("Enable Email Notifications", 
                                   value=settings.notify_email if settings and hasattr(settings, 'notify_email') else False,
                                   help="Send email alerts for high-score tenders")
        
        if email_enabled:
            st.info("📧 Email notifications will be sent for new tenders scoring above the threshold.")
            
            col1, col2 = st.columns(2)
            
            with col1:
                email_recipients = st.text_area("Recipients (comma-separated)", 
                                               value=settings.email_recipients if settings and hasattr(settings, 'email_recipients') else "",
                                               placeholder="email1@example.com, email2@example.com",
                                               help="Enter email addresses separated by commas")
                
                smtp_server = st.text_input("SMTP Server",
                                           value=settings.smtp_server if settings and hasattr(settings, 'smtp_server') else "smtp.gmail.com",
                                           placeholder="smtp.gmail.com")
            
            with col2:
                smtp_port = st.number_input("SMTP Port",
                                           value=settings.smtp_port if settings and hasattr(settings, 'smtp_port') else 587,
                                           min_value=1, max_value=65535)
                
                smtp_username = st.text_input("SMTP Username",
                                             value=settings.smtp_username if settings and hasattr(settings, 'smtp_username') else "",
                                             placeholder="your.email@gmail.com")
                
                smtp_password = st.text_input("SMTP Password", 
                                             type="password",
                                             value="",
                                             placeholder="App Password (not regular password)",
                                             help="For Gmail, use an App Password from your Google Account settings")
            
            # Test email button
            if st.button("📤 Send Test Email", key="test_email_btn"):
                if smtp_username and smtp_password and email_recipients:
                    try:
                        from app.notifications import send_email_notification
                        
                        # Create a mock tender for testing
                        class MockTender:
                            def __init__(self):
                                self.title = "TEST: Sample Tender Title"
                                self.title_translated = "TEST: Sample Tender Title"
                                self.score = 85.0
                                self.category = "Case & Complaint Management"
                                self.buyer = "Test Organization"
                                self.country = "Kenya"
                                self.deadline = "2025-12-31"
                                self.link = "https://example.com/tender/123"
                        
                        # Create mock settings with current values
                        class MockSettings:
                            pass
                        
                        mock_settings = MockSettings()
                        mock_settings.email_recipients = email_recipients
                        mock_settings.smtp_server = smtp_server
                        mock_settings.smtp_port = smtp_port
                        mock_settings.smtp_username = smtp_username
                        mock_settings.smtp_password = smtp_password
                        
                        # Send test email
                        success = send_email_notification(mock_settings, [MockTender()])
                        if success:
                            st.success("✅ Test email sent successfully! Check your inbox.")
                        else:
                            st.error("❌ Failed to send test email. Check your SMTP settings.")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
                else:
                    st.warning("⚠️ Please fill in SMTP settings and recipients first.")
        
        st.markdown("---")
        
        # Save button
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("💾 Save Settings", key="save_settings_button", type="primary", use_container_width=True):
                if settings:
                    settings.notifications_enabled = notification_enabled
                    settings.min_score_to_notify = float(min_score)
                    settings.notify_email = email_enabled if 'email_enabled' in dir() else False
                    if email_enabled:
                        settings.email_recipients = email_recipients
                        settings.smtp_server = smtp_server
                        settings.smtp_port = smtp_port
                        settings.smtp_username = smtp_username
                        if smtp_password:
                            settings.smtp_password = smtp_password
                    db.session.commit()
                    st.success("✅ Settings saved!")
                else:
                    new_settings = AppSettings(
                        notifications_enabled=notification_enabled,
                        min_score_to_notify=float(min_score),
                        notify_email=email_enabled if 'email_enabled' in dir() else False
                    )
                    if email_enabled:
                        new_settings.email_recipients = email_recipients
                        new_settings.smtp_server = smtp_server
                        new_settings.smtp_port = smtp_port
                        new_settings.smtp_username = smtp_username
                        if smtp_password:
                            new_settings.smtp_password = smtp_password
                    db.session.add(new_settings)
                    db.session.commit()
                    st.success("✅ Settings saved!")
        
        st.markdown("---")
        
        # ML Learning Section
        st.subheader("🤖 Machine Learning")
        st.markdown("""
        TenderWatch learns from your saved and favorited tenders to improve relevance scoring.
        The more tenders you save, the smarter it gets!
        """)
        
        # Show ML status
        try:
            from app.ml_ranker import get_model_status, train_ranker_model, update_golden_embeddings
            
            ml_status = get_model_status()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                status_icon = "✅" if ml_status.get('sentence_model_loaded') else "❌"
                st.metric("Sentence Model", status_icon)
            with col2:
                status_icon = "✅" if ml_status.get('ranker_model_loaded') else "⚪"
                st.metric("Ranker Model", status_icon)
            with col3:
                st.metric("Golden Tenders", ml_status.get('golden_tenders_count', 0))
            
            if ml_status.get('ranker_trained_at'):
                st.caption(f"Model trained: {ml_status['ranker_trained_at'][:10]} on {ml_status.get('ranker_positive_count', 0)} positive samples")
            
            # Train button
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Update Golden Embeddings", help="Update semantic model with saved/favorited tenders"):
                    with st.spinner("Updating embeddings..."):
                        success = update_golden_embeddings()
                        if success:
                            st.success("✅ Golden embeddings updated!")
                        else:
                            st.warning("⚠️ No saved/favorited tenders to learn from yet")
            
            with col2:
                if st.button("🎓 Train Ranker Model", help="Train ML model to rank tenders based on your preferences"):
                    with st.spinner("Training model..."):
                        success, message = train_ranker_model()
                        if success:
                            st.success(f"✅ {message}")
                        else:
                            st.warning(f"⚠️ {message}")
        
        except ImportError as e:
            st.warning(f"⚠️ ML features not available: {e}")
            st.caption("Install with: pip install sentence-transformers lightgbm")
        except Exception as e:
            st.error(f"ML error: {e}")
        
        st.markdown("---")
        
        st.subheader("📊 Database Statistics")
        stats = get_stats()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Tenders in Database", stats['total'])
            st.metric("Active Sources", stats['active_sources'])
        
        with col2:
            st.metric("Saved Tenders", stats['saved'])
            st.metric("Favorite Tenders", stats['favorites'])
        
        st.markdown("---")
        
        st.subheader("ℹ️ About")
        st.markdown("""
        **TenderWatch v2.0** - Streamlit Edition
        
        Automated tender scanning and opportunity tracking for cBrain's F2 platform.
        
        - 🔍 Intelligent keyword-based scoring
        - 📊 Automatic categorization
        - 🌐 Multi-source scanning
        - 💾 Persistent storage
        - 📲 Installable as app (PWA)
        - 🔔 Daily notification reminders
        
        For support, see the documentation.
        """)
