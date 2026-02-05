"""
TenderWatch - Streamlit Version
Simple, powerful tender scanning for cBrain F2 Platform
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json

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
app = create_app()

def init_db():
    """Initialize database with app context"""
    with app.app_context():
        db.create_all()
        
        # Run AI database migration on startup
        try:
            from sqlalchemy import text
            # Try to add AI columns if they don't exist
            ai_columns = [
                "ALTER TABLE tender_result ADD COLUMN semantic_score FLOAT DEFAULT 0.0",
                "ALTER TABLE tender_result ADD COLUMN ai_confidence FLOAT DEFAULT 0.0",
                "ALTER TABLE tender_result ADD COLUMN entities_extracted TEXT DEFAULT ''",
                "ALTER TABLE tender_result ADD COLUMN ai_summary TEXT DEFAULT ''",
                "ALTER TABLE app_settings ADD COLUMN ai_scoring_enabled BOOLEAN DEFAULT 1",
                "ALTER TABLE app_settings ADD COLUMN ai_learning_enabled BOOLEAN DEFAULT 1",
                "ALTER TABLE app_settings ADD COLUMN entity_extraction_enabled BOOLEAN DEFAULT 1",
            ]
            for sql in ai_columns:
                try:
                    db.session.execute(text(sql))
                    db.session.commit()
                except:
                    db.session.rollback()  # Column already exists, continue
            
            # Run auto-discovery migration on startup
            discovery_columns = [
                "ALTER TABLE tender_result ADD COLUMN discovery_method VARCHAR(50) DEFAULT 'manual'",
                "ALTER TABLE tender_result ADD COLUMN search_query VARCHAR(500)",
                "ALTER TABLE tender_result ADD COLUMN search_source VARCHAR(50)",
                "ALTER TABLE app_settings ADD COLUMN auto_discovery_enabled BOOLEAN DEFAULT 1",
                "ALTER TABLE app_settings ADD COLUMN google_api_key VARCHAR(500) DEFAULT ''",
                "ALTER TABLE app_settings ADD COLUMN google_cx VARCHAR(500) DEFAULT ''",
                "ALTER TABLE app_settings ADD COLUMN bing_api_key VARCHAR(500) DEFAULT ''",
                "ALTER TABLE app_settings ADD COLUMN discovery_queries TEXT DEFAULT ''",
                "ALTER TABLE app_settings ADD COLUMN results_per_query INTEGER DEFAULT 10",
            ]
            for sql in discovery_columns:
                try:
                    db.session.execute(text(sql))
                    db.session.commit()
                except:
                    db.session.rollback()  # Column already exists, continue
            
            # Create DiscoveryLog table if it doesn't exist
            try:
                db.session.execute(text("""
                    CREATE TABLE IF NOT EXISTS discovery_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_type VARCHAR(50) NOT NULL,
                        queries_run INTEGER DEFAULT 0,
                        results_found INTEGER DEFAULT 0,
                        results_saved INTEGER DEFAULT 0,
                        google_quota_used INTEGER DEFAULT 0,
                        bing_quota_used INTEGER DEFAULT 0,
                        execution_time_seconds REAL DEFAULT 0.0,
                        error_message TEXT DEFAULT '',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                db.session.commit()
            except:
                db.session.rollback()
        except:
            pass  # Migration not critical for startup
        
        # Ensure settings exist
        if not AppSettings.query.first():
            settings = AppSettings()
            db.session.add(settings)
            db.session.commit()
        
        # Ensure default sources exist
        if TenderSource.query.count() == 0:
            default_sources = [
                # Kenya-specific sources
                TenderSource(name="UNDP Kenya Opportunities", url="https://procurement-notices.undp.org/view_notices.cfm?static_type=notice_type&value=bid&x=19&y=12&country=&lng=", active=True, favorite=True),
                TenderSource(name="World Bank Kenya Tenders", url="https://www.worldbank.org/en/projects-operations/products-and-services/brief/summary-and-detailed-borrower-procurement-reports", active=True, favorite=False),
                TenderSource(name="USAID Kenya Procurement", url="https://www.usaid.gov/work-usaid/how-to-work-with-usaid/opportunities", active=True, favorite=False),
                TenderSource(name="AfDB Tender Portal", url="https://www.afdb.org/en/projects-and-operations/procurement", active=True, favorite=False),
                
                # Global sources
                TenderSource(name="UNDB Global", url="https://www.undb.org/", active=True, favorite=False),
                TenderSource(name="GEF Procurement", url="https://www.thegef.org/projects-operations/procurement", active=True, favorite=False),
                TenderSource(name="IFC Tenders", url="https://www.ifc.org/en/what-we-do", active=True, favorite=False),
                TenderSource(name="UNOPS Tenders", url="https://www.unops.org/procurement-opportunities", active=True, favorite=True),
            ]
            for source in default_sources:
                db.session.add(source)
            db.session.commit()
            print("✅ Added default tender sources")

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
                    TenderResult.description.ilike(search_term)
                )
            if filters.get('favorites_only'):
                query = query.filter(TenderResult.favorite == True)
            if filters.get('saved_only'):
                query = query.filter(TenderResult.saved == True)
        
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
        new_tenders = run_scan()
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
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown("✨ Let's discover some amazing opportunities together!")
    
    with col2:
        if st.button("🚀 Let's Go!", key="top_scan_button", type="primary", use_container_width=True):
            with st.spinner("🔮 Working some magic..."):
                new_tenders = run_tender_scan()
                if new_tenders:
                    st.success(f"🎉 Woohoo! Found {len(new_tenders)} awesome opportunities!")
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
            csv_data = "Title,Link,Score,Category,Country,Deadline,Description\n"
            for t in all_tenders_for_export:
                csv_data += f'"{t.title}","{t.link}",{t.score},"{t.category or ""}","{t.country or ""}","{t.deadline or ""}","{(t.description or "")[:200]}"\n'
            
            st.download_button(
                label="📥 Export CSV",
                data=csv_data,
                file_name=f"tenders_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                help="Download all tenders as CSV"
            )
    
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
        search = st.text_input("🔍 Search", placeholder="Search titles & descriptions...", help="Search in tender titles and descriptions")
    
    # Get filtered tenders
    filters = {
        'min_score': min_score,
        'category': category,
        'sort_by': sort_by,
        'search': search
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
                # Header row
                col_title, col_score = st.columns([5, 1])
                with col_title:
                    st.markdown(f"### {tender.title}")
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
            <div style='font-size: 4rem; margin-bottom: 1rem; animation: bounce 2s infinite; cursor: pointer;' 
                 onclick='document.getElementById("bullseye_scan").click();'>🎯</div>
            <h3 style='color: #8b5cf6; margin-bottom: 1rem; font-weight: 700;'>Ready for the Hunt?</h3>
            <p style='color: #6b7280; font-size: 1.1rem; margin-bottom: 0.5rem;'>
                Let's discover some amazing tenders together! 🚀
            </p>
            <p style='color: #a3a3a3; font-size: 0.85rem; margin-top: 0.5rem; font-style: italic;'>👆 Click the target above!</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Hidden button that gets triggered by the emoji
        if st.button("🎯", key="bullseye_scan", help="Click to scan!"):
            with st.spinner("🔮 Working some magic..."):
                new_tenders = run_tender_scan()
                if new_tenders:
                    st.success(f"🎉 Woohoo! Found {len(new_tenders)} awesome opportunities!")
                else:
                    st.info("🤔 Hmm, nothing new right now. Check back soon!")
                st.rerun()
        
        st.markdown("""
        <style>
        /* Hide the actual Streamlit button */
        button[data-testid="baseButton-secondary"] {
            display: none !important;
        }
        </style>
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
        
        st.subheader("🔄 Auto-Scan Settings")
        
        auto_scan = st.checkbox("Enable Automatic Scanning", value=settings.auto_scan_enabled if settings else False)
        scan_interval = st.number_input("Scan Interval (minutes)", min_value=5, max_value=1440, 
                                       value=settings.scan_interval_minutes if settings else 60)
        
        notification_enabled = st.checkbox("Enable Notifications", 
                                          value=settings.notifications_enabled if settings and hasattr(settings, 'notifications_enabled') else False)
        
        st.markdown("---")
        
        # Auto-Discovery Settings
        st.markdown("""
            <div style='padding: 1rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 16px; margin-bottom: 1rem;'>
                <div style='font-size: 2rem; text-align: center; margin-bottom: 0.5rem;'>🌐</div>
                <div style='text-align: center; color: white; font-weight: 600; font-size: 1.2rem;'>Auto-Discovery (Google + Bing APIs)</div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        Automatically discover tenders across the entire web without manual source management.
        
        **Free Tier:** 
        - 🔍 Google: 100 searches/day
        - 🔎 Bing: 33 searches/day  
        - ⚡ Total: **133 free searches daily**
        """)
        
        auto_discovery = st.checkbox("Enable Auto-Discovery", 
                                     value=settings.auto_discovery_enabled if settings and hasattr(settings, 'auto_discovery_enabled') else True,
                                     help="Automatically find tenders via search APIs")
        
        if auto_discovery:
            st.info("📚 **Setup Required:** Get free API keys from [Google](https://developers.google.com/custom-search) and [Bing](https://www.microsoft.com/en-us/bing/apis/bing-web-search-api). See `AUTO_DISCOVERY_SETUP.md` for guide.")
            
            google_key = st.text_input("Google Custom Search API Key", 
                                       value=settings.google_api_key if settings and hasattr(settings, 'google_api_key') else "",
                                       type="password",
                                       help="Get from Google Cloud Console")
            
            google_cx = st.text_input("Google Custom Search Engine ID (CX)", 
                                     value=settings.google_cx if settings and hasattr(settings, 'google_cx') else "",
                                     help="Create at programmablesearchengine.google.com")
            
            bing_key = st.text_input("Bing Search API Key", 
                                    value=settings.bing_api_key if settings and hasattr(settings, 'bing_api_key') else "",
                                    type="password",
                                    help="Get from Azure Portal")
            
            results_per_query = st.number_input("Results per Query", min_value=5, max_value=50,
                                               value=settings.results_per_query if settings and hasattr(settings, 'results_per_query') else 10,
                                               help="Lower = fewer API calls, faster scans")
            
            custom_queries = st.text_area("Custom Search Queries (JSON array, optional)",
                                         value=settings.discovery_queries if settings and hasattr(settings, 'discovery_queries') else "",
                                         height=100,
                                         placeholder='["RFP document management Kenya", "tender case management"]',
                                         help="Leave empty to use default queries")
        
        st.markdown("---")
        
        # Modern settings sections with icons
        st.markdown("""
            <div style='padding: 1rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 16px; margin-bottom: 1rem;'>
                <div style='font-size: 2rem; text-align: center; margin-bottom: 0.5rem;'>📱</div>
                <div style='text-align: center; color: white; font-weight: 600; font-size: 1.2rem;'>Push Notifications</div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        Receive instant alerts for new high-score tenders on your phone or desktop browser.
        
        **Browser Support:**
        - ✅ Android: Chrome, Firefox, Edge, Samsung Internet
        - ✅ iOS: Safari 16.4+ (requires iOS 16.4 or later)
        - ✅ Desktop: Chrome, Firefox, Edge, Safari
        """)
        
        # Check if notifications are supported
        push_enabled = st.checkbox("🔔 Enable Push Notifications", value=False, 
                                   help="Get instant alerts when new tenders match your keywords")
        
        if push_enabled:
            st.info("""
            **📲 How to enable:**
            1. Click "Subscribe to Notifications" below
            2. Allow notifications when your browser asks
            3. You'll receive alerts for tenders scoring ≥70%
            
            **Note:** For best results, deploy on HTTPS (Streamlit Cloud, Railway, or Render provide free HTTPS).
            """)
            
            # This will be handled by JavaScript in production
            if st.button("🔔 Subscribe to Notifications", type="primary"):
                st.warning("""
                ⚠️ **Push notifications require HTTPS deployment**
                
                To enable full push notification support:
                1. Deploy to Streamlit Cloud (free HTTPS automatic)
                2. Or deploy Flask version with PWA support
                3. See `MOBILE_NOTIFICATIONS_SETUP.md` for complete guide
                
                For now, desktop notifications work without HTTPS.
                """)
        
        min_score = st.slider("Minimum Score for Notifications", 0, 100, 
                             value=int(settings.min_score_to_notify) if settings else 70,
                             help="Only notify for tenders above this score")
        
        st.markdown("---")
        
        # Save button with modern styling
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("💾 Save Settings", key="save_settings_button", type="primary", use_container_width=True):
                if settings:
                    settings.auto_scan_enabled = auto_scan
                    settings.scan_interval_minutes = scan_interval
                    settings.notifications_enabled = notification_enabled
                    settings.min_score_to_notify = float(min_score)
                    
                    # Save auto-discovery settings
                    if hasattr(settings, 'auto_discovery_enabled'):
                        settings.auto_discovery_enabled = auto_discovery
                        settings.google_api_key = google_key if auto_discovery else ""
                        settings.google_cx = google_cx if auto_discovery else ""
                        settings.bing_api_key = bing_key if auto_discovery else ""
                        settings.results_per_query = results_per_query if auto_discovery else 10
                        settings.discovery_queries = custom_queries if auto_discovery else ""
                    
                    db.session.commit()
                    st.success("✅ Settings saved! Auto-discovery will run on next scan.")
                else:
                    new_settings = AppSettings(
                        auto_scan_enabled=auto_scan,
                        scan_interval_minutes=scan_interval,
                        notifications_enabled=notification_enabled,
                        min_score_to_notify=float(min_score)
                    )
                    db.session.add(new_settings)
                    db.session.commit()
                    st.success("✅ Settings saved! Run migration script to enable auto-discovery.")
        
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
        
        For support, see [documentation](README.md).
        """)
