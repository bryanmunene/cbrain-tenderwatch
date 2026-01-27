"""
TenderWatch - Streamlit Version
Simple, powerful tender scanning for cBrain F2 Platform
"""

import streamlit as st
import pandas as pd
from datetime import datetime
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

# Custom CSS for cBrain branding
st.markdown("""
<style>
    .main {
        background-color: #0f172a;
        color: #e2e8f0;
    }
    .stButton>button {
        background-color: #1e3a8a;
        color: white;
        border-radius: 8px;
        padding: 0.5rem 2rem;
        font-weight: 600;
    }
    .stButton>button:hover {
        background-color: #0f766e;
    }
    h1, h2, h3 {
        color: #60a5fa;
    }
    .metric-card {
        background-color: #1e293b;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #0f766e;
    }
    .tender-card {
        background-color: #1e293b;
        padding: 1.5rem;
        border-radius: 8px;
        margin-bottom: 1rem;
        border: 1px solid #334155;
    }
    .high-score {
        color: #10b981;
        font-weight: bold;
    }
    .medium-score {
        color: #f59e0b;
        font-weight: bold;
    }
    .low-score {
        color: #ef4444;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Flask app context for database
app = create_app()

def init_db():
    """Initialize database with app context"""
    with app.app_context():
        db.create_all()
        # Ensure settings exist
        if not AppSettings.query.first():
            settings = AppSettings()
            db.session.add(settings)
            db.session.commit()

def get_tenders(filters=None):
    """Get tenders with optional filters"""
    with app.app_context():
        query = TenderResult.query
        
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
    """Get dashboard statistics"""
    with app.app_context():
        total = TenderResult.query.count()
        high_score = TenderResult.query.filter(TenderResult.score >= 70).count()
        saved = TenderResult.query.filter_by(saved=True).count()
        favorites = TenderResult.query.filter_by(favorite=True).count()
        active_sources = TenderSource.query.filter_by(active=True).count()
        
        # Get categories
        categories = db.session.query(
            TenderResult.category,
            db.func.count(TenderResult.id).label('count')
        ).group_by(TenderResult.category).all()
        
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
    st.markdown("**cBrain F2 Platform**")
    st.markdown("---")
    
    page = st.radio(
        "Navigation",
        ["📊 Dashboard", "🔍 Scan & Results", "📁 Sources", "⭐ Favorites", "💾 Saved", "⚙️ Settings"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    st.caption("© 2026 cBrain TenderWatch")

# Main content based on selected page
if page == "📊 Dashboard":
    st.title("📊 Dashboard")
    
    stats = get_stats()
    
    # Metrics row
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total Tenders", stats['total'])
    with col2:
        st.metric("High Score (≥70%)", stats['high_score'])
    with col3:
        st.metric("Saved", stats['saved'])
    with col4:
        st.metric("Favorites", stats['favorites'])
    with col5:
        st.metric("Active Sources", stats['active_sources'])
    
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
            st.bar_chart(cat_df.set_index('Category'))
        
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
                    if st.button("View", key=f"view_recent_{tender.id}"):
                        st.session_state['view_tender'] = tender.id
                        st.rerun()
                
                st.markdown("---")
    else:
        st.info("No tenders found. Run a scan to discover opportunities!")

elif page == "🔍 Scan & Results":
    st.title("🔍 Tender Scanning")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown("Scan all active tender sources to discover new opportunities")
    
    with col2:
        if st.button("🔄 Run Scan Now", type="primary", use_container_width=True):
            with st.spinner("🔍 Scanning tender sources..."):
                new_tenders = run_tender_scan()
                if new_tenders:
                    st.success(f"✅ Found {len(new_tenders)} new tenders!")
                else:
                    st.info("No new tenders found.")
                st.rerun()
    
    st.markdown("---")
    
    # Filters
    st.subheader("🎛️ Filters")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        min_score = st.slider("Minimum Score", 0, 100, 0, 5)
    
    with col2:
        categories = ["All"] + list(set([t.category for t in get_tenders() if t.category]))
        category = st.selectbox("Category", categories)
    
    with col3:
        sort_by = st.selectbox("Sort By", ["score", "date", "deadline"])
    
    with col4:
        search = st.text_input("🔍 Search", placeholder="Keywords...")
    
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
            score_color = "#10b981" if tender.score >= 70 else "#f59e0b" if tender.score >= 40 else "#ef4444"
            
            with st.expander(f"**[{tender.score:.1f}%]** {tender.title}", expanded=False):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"**Category:** {tender.category} ({tender.confidence:.0%} confidence)")
                    st.markdown(f"**Country:** {tender.country or 'N/A'}")
                    st.markdown(f"**Deadline:** {tender.deadline or 'Not specified'}")
                    st.markdown(f"**Description:** {tender.description[:300]}...")
                    
                    # Scoring breakdown
                    if tender.scoring_breakdown:
                        try:
                            breakdown = json.loads(tender.scoring_breakdown)
                            st.markdown("**Matched Keywords:**")
                            keywords = breakdown.get('unique_keywords', [])[:10]
                            st.caption(", ".join(keywords) if keywords else "None")
                        except:
                            pass
                    
                    st.link_button("🔗 View Original Tender", tender.link, use_container_width=False)
                
                with col2:
                    st.markdown(f"**Score: <span style='color:{score_color};font-size:24px;'>{tender.score:.1f}%</span>**", unsafe_allow_html=True)
                    
                    if st.button("⭐ Favorite" if not tender.favorite else "⭐ Unfavorite", 
                                key=f"fav_{tender.id}"):
                        toggle_favorite(tender.id)
                        st.rerun()
                    
                    if st.button("💾 Save" if not tender.saved else "💾 Unsave", 
                                key=f"save_{tender.id}"):
                        toggle_saved(tender.id)
                        st.rerun()
    else:
        st.info("No tenders match your filters. Try adjusting the criteria or run a new scan.")

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
                        if st.button("Toggle", key=f"toggle_{source.id}"):
                            toggle_source(source.id)
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
            st.warning("No sources configured. Add sources to start scanning!")
    
    with tab2:
        st.markdown("### Add New Tender Source")
        
        with st.form("add_source_form"):
            name = st.text_input("Source Name", placeholder="e.g., UNDP Kenya")
            url = st.text_input("Source URL", placeholder="https://...")
            
            submitted = st.form_submit_button("➕ Add Source", type="primary")
            
            if submitted:
                if name and url:
                    add_source(name, url)
                    st.success(f"✅ Added source: {name}")
                    st.rerun()
                else:
                    st.error("Please provide both name and URL")

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
                                          value=settings.notification_enabled if settings else False)
        
        if st.button("💾 Save Settings", type="primary"):
            if settings:
                settings.auto_scan_enabled = auto_scan
                settings.scan_interval_minutes = scan_interval
                settings.notification_enabled = notification_enabled
                db.session.commit()
                st.success("✅ Settings saved!")
            else:
                new_settings = AppSettings(
                    auto_scan_enabled=auto_scan,
                    scan_interval_minutes=scan_interval,
                    notification_enabled=notification_enabled
                )
                db.session.add(new_settings)
                db.session.commit()
                st.success("✅ Settings saved!")
        
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
