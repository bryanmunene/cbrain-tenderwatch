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
        --bg-secondary: {'#1e293b' if st.session_state.theme == 'dark' else '#f8fafc'};
        --text-primary: {'#f1f5f9' if st.session_state.theme == 'dark' else '#1e293b'};
        --text-secondary: {'#94a3b8' if st.session_state.theme == 'dark' else '#64748b'};
        --border-color: {'#334155' if st.session_state.theme == 'dark' else '#e2e8f0'};
        --card-bg: {'#1e293b' if st.session_state.theme == 'dark' else '#ffffff'};
    }}
    
    /* Main background */
    .main {{
        background: {'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)' if st.session_state.theme == 'dark' else 'linear-gradient(135deg, #f8fafc 0%, #e0e7ff 100%)'};
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
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 12px;
        padding: 0.75rem 2rem;
        font-weight: 600;
        border: none;
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
        transition: all 0.3s ease;
    }}
    
    .stButton>button:hover {{
        transform: translateY(-2px);
        box-shadow: 0 8px 16px rgba(102, 126, 234, 0.4);
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
        except:
            pass  # Migration not critical for startup
        
        # Ensure settings exist
        if not AppSettings.query.first():
            settings = AppSettings()
            db.session.add(settings)
            db.session.commit()

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
    
    # Dark mode toggle
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("**Theme**")
    with col2:
        if st.button("🌓"):
            st.session_state.theme = 'dark' if st.session_state.theme == 'light' else 'light'
            st.rerun()
    
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
    st.markdown("Overview of all tender opportunities")
    
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
        st.info("📭 No tenders found yet.")
        st.markdown("""\n**Get started:**
1. Click **🔍 Scan & Results** in the sidebar
2. Click **🔄 Run Scan Now** to find tenders
3. Or add tender sources in **📁 Sources**
        """)

elif page == "🔍 Scan & Results":
    st.title("🔍 Tender Scanning")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown("Scan all active tender sources to discover new opportunities")
    
    with col2:
        if st.button("🔄 Run Scan Now", key="top_scan_button", type="primary", use_container_width=True):
            with st.spinner("🔍 Scanning tender sources..."):
                new_tenders = run_tender_scan()
                if new_tenders:
                    st.success(f"✅ Found {len(new_tenders)} new tenders!")
                else:
                    st.info("No new tenders found.")
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
                score_label = "Highly Relevant"
                score_class = "high-score"
            elif tender.score >= 40:
                score_emoji = "📊"
                score_color = "#f59e0b"
                score_label = "Good Match"
                score_class = "medium-score"
            else:
                score_emoji = "📝"
                score_color = "#ef4444"
                score_label = "Potential Match"
                score_class = "low-score"
            
            # Create attractive card with modern styling
            with st.container():
                st.markdown(f"""
                    <div style='background: var(--card-bg); padding: 1.5rem; border-radius: 16px; border: 1px solid var(--border-color); box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); margin-bottom: 1rem; transition: all 0.3s ease;'>
                        <div style='display: flex; justify-content: space-between; align-items: start; margin-bottom: 1rem;'>
                            <h3 style='margin: 0; color: var(--text-primary); flex: 1;'>{tender.title}</h3>
                            <span class='{score_class}' style='margin-left: 1rem; white-space: nowrap;'>{score_emoji} {tender.score:.0f}%</span>
                        </div>
                        <div style='display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1rem;'>
                            {f'<span style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 0.25rem 0.75rem; border-radius: 8px; font-size: 0.85rem;">📁 {tender.category}</span>' if tender.category else ''}
                            {f'<span style="background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%); color: white; padding: 0.25rem 0.75rem; border-radius: 8px; font-size: 0.85rem;">🌍 {tender.country}</span>' if tender.country else ''}
                            {f'<span style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); color: white; padding: 0.25rem 0.75rem; border-radius: 8px; font-size: 0.85rem;">⏰ {tender.deadline}</span>' if tender.deadline else ''}
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                
                # Details section
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    if tender.description:
                        st.markdown(f"**📄 Description**")
                        st.write(tender.description[:200] + ("..." if len(tender.description) > 200 else ""))
                    
                    # Keywords
                    if tender.scoring_breakdown:
                        try:
                            breakdown = json.loads(tender.scoring_breakdown)
                            keywords = breakdown.get('unique_keywords', [])[:8]
                            if keywords:
                                st.markdown("**🏷️ Matched Keywords**")
                                keyword_badges = " ".join([f"<span style='background: #e0e7ff; color: #4338ca; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.85rem; margin-right: 0.3rem;'>{kw}</span>" for kw in keywords])
                                st.markdown(keyword_badges, unsafe_allow_html=True)
                        except:
                            pass
                
                with col2:
                    st.markdown("**📍 Details**")
                    st.write(f"🌍 {tender.country or 'Global'}")
                    if tender.deadline:
                        st.write(f"⏰ {tender.deadline}")
                    else:
                        st.write("⏰ No deadline set")
                
                with col3:
                    st.markdown("**⚡ Actions**")
                    
                    col_a, col_b = st.columns(2)
                    with col_a:
                        fav_icon = "⭐" if tender.favorite else "☆"
                        if st.button(fav_icon, key=f"fav_{tender.id}", help="Toggle favorite"):
                            toggle_favorite(tender.id)
                            st.rerun()
                    
                    with col_b:
                        save_icon = "💾" if tender.saved else "📥"
                        if st.button(save_icon, key=f"save_{tender.id}", help="Toggle saved"):
                            toggle_saved(tender.id)
                            st.rerun()
                    
                    st.link_button("🔗 View Source", tender.link, use_container_width=True)
                    
                    if st.button("📖 Full Details", key=f"detail_{tender.id}", use_container_width=True):
                        st.session_state['selected_tender'] = tender.id
                        st.info("💡 Click 'View Source' above to see the full tender document")
                
                st.markdown("---")
    else:
        st.markdown("""
        <div style='text-align: center; padding: 3rem; background: rgba(255,255,255,0.95); 
                    border-radius: 20px; margin: 2rem 0;'>
            <div style='font-size: 4rem; margin-bottom: 1rem;'>📭</div>
            <h3 style='color: #2ba8d8; margin-bottom: 1rem;'>No Tenders Found</h3>
            <p style='color: #6b7280; font-size: 1.1rem; margin-bottom: 2rem;'>
                Adjust your filters or run a fresh scan to discover new opportunities!
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🔄 Run Scan Now", key="main_scan_button", type="primary", use_container_width=True):
                with st.spinner("🔍 Scanning tender sources..."):
                    new_tenders = run_tender_scan()
                    if new_tenders:
                        st.success(f"✅ Found {len(new_tenders)} new tenders!")
                    else:
                        st.info("No new tenders found.")
                    st.rerun()

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
                                          value=settings.notification_enabled if settings else False)
        
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
                    settings.notification_enabled = notification_enabled
                    settings.min_score_to_notify = float(min_score)
                    db.session.commit()
                    st.success("✅ Settings saved!")
                else:
                    new_settings = AppSettings(
                        auto_scan_enabled=auto_scan,
                        scan_interval_minutes=scan_interval,
                        notification_enabled=notification_enabled,
                        min_score_to_notify=float(min_score)
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
