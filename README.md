# TenderWatch - cBrain F2 Platform

A sophisticated tender scanning and opportunity tracking application designed for cBrain's F2 platform. TenderWatch automates the discovery and ranking of tender opportunities from both Kenya-specific and global sources, providing intelligent scoring and detailed analysis.

## 🎯 Now Available in 2 Versions!

### ⭐ Streamlit Version (Recommended - Simpler)
- **One file** (`streamlit_app.py`) - everything in 600 lines
- **Pure Python** - no HTML/CSS/templates needed
- **Auto-generated UI** - beautiful interface built automatically
- **1-click deploy** - free on Streamlit Cloud forever
- **Faster development** - changes appear instantly

### 🔧 Flask Version (Original - Full Control)
- **Traditional web app** - routes, templates, full customization
- **Complete control** - customize every aspect of UI
- **Professional structure** - separation of concerns
- **Production-ready** - deploy anywhere (Railway, Render, Heroku)

**Both versions use the same backend** (scraper, scoring, database) - just different frontends!

---

## Features

### 🎯 Core Functionality

- **Automated Tender Scanning**: Scan multiple tender sources simultaneously to discover opportunities
- **Intelligent Scoring System**: AI-driven scoring based on keyword matching and relevance analysis
  - Scores range from 0-100% based on relevance to cBrain's domain
  - Detailed scoring breakdown showing matched keywords and categories
  - Source bias adjustments for premium tender sources

- **Tender Categorization**: Automatic classification into categories:
  - EDMS / Records Management
  - Case / Workflow Management
  - ICT / Software Solutions
  - Procurement / Consulting
  - Infrastructure / Construction

- **Advanced Filtering & Sorting**:
  - Sort by relevance score (highest first)
  - Sort by deadline (earliest first)
  - Sort by newest opportunities
  - Filter by favorites and saved tenders

### ⭐ User Features

- **Favorite Management**: Mark important tenders and sources as favorites
- **Tender Saving**: Save relevant tenders for later review
- **Detailed Tender View**: Comprehensive tender information including:
  - Full tender title and description
  - Direct access links to original sources
  - Scoring breakdown with explanation
  - Matched keywords and categories
  - Classification confidence metrics
  - Deadline information

- **Source Management**:
  - Add custom tender sources
  - Manage source preferences (active/inactive)
  - Mark favorite sources
  - Direct links to source websites

### 🎨 UI/UX

- **cBrain-Themed Design**: Professional styling aligned with cBrain's brand
  - Primary Color: Deep Blue (#1e3a8a)
  - Secondary Color: Teal (#0f766e)
  - Accent Color: Red (#dc2626)
  - Dark theme optimized for extended use

- **Responsive Layout**: Works seamlessly on desktop and tablet devices
- **Intuitive Navigation**: Clear menu structure with icon-based navigation
- **Performance-Optimized**: Bootstrap 5 for fast loading and smooth interactions

## Installation & Setup

### Choose Your Version

#### 🌟 Streamlit (Simpler - Recommended for Most Users)

**3 Easy Steps:**

```bash
cd tenderwatch_app
pip install -r requirements.txt
python init_sources.py
streamlit run streamlit_app.py    # Opens automatically at http://localhost:8501
```

**Deploy Online (1-Click):**
1. Push to GitHub
2. Go to [streamlit.io/cloud](https://streamlit.io/cloud)
3. Click "New app" → Select your repo → Deploy
4. Done! Get: `https://your-app.streamlit.app`

**📖 Full guide:** [STREAMLIT_GUIDE.md](STREAMLIT_GUIDE.md)

---

#### 🔧 Flask (Original - Full Control)

**3 Easy Steps:**

```bash
cd tenderwatch_app
pip install -r requirements.txt
python init_sources.py
python run.py                      # Opens at http://localhost:5000
```

**Deploy Online:**
- **Railway:** railway.app → Deploy from GitHub
- **Render:** render.com → New Web Service
- **Heroku:** `heroku create && git push heroku main`

**📖 Full guide:** [DEPLOYMENT.md](DEPLOYMENT.md)

---

## Usage Guide

### Dashboard / Scan Results

1. **Run Scan**: Click "Run Scan" to search all active sources for tender opportunities
2. **View Results**: Results are displayed in a table sorted by score (highest first)
3. **Sort Options**:
   - By Score: Most relevant opportunities first
   - By Newest: Recently added tenders
   - By Deadline: Earliest deadlines first

### Viewing Tender Details

1. Click the tender title or the **Eye** icon to view detailed information
2. On the detail page, you'll see:
   - Complete tender information
   - Scoring breakdown showing which keywords matched
   - Direct link to the original tender source
   - Option to save or favorite the tender

### Managing Favorites

- **Favorite Tenders**: Click the star icon to mark a tender as favorite
- **View Favorites**: Navigate to "Favorites" in the menu to see all starred tenders
- **Favorite Sources**: In the Sources page, star frequently-used tender sources

### Managing Sources

1. **Add New Source**:
   - Go to "Sources" menu
   - Enter source name and URL
   - Click "Add Source"

2. **Manage Sources**:
   - Toggle active/inactive status
   - Mark as favorite for quick access
   - Visit source website directly
   - Delete sources you no longer need

## Scoring System

### How It Works

The scoring system analyzes tender titles and descriptions to determine relevance to cBrain's platforms:

#### Keyword Matching (Base Score)
- Tender text is scanned for predefined keywords related to:
  - Records management (document, edms, archives, etc.)
  - Case management (workflow, complaint, permit, etc.)
  - Technology (platform, portal, system, software, etc.)
  - Procurement (tender, bid, rfp, rfq, etc.)

- **Score Calculation**: `(Matched Keywords / Total Keywords) × 100`

#### Score Modifiers
- **Source Bias**: Premium sources (UNDP, World Bank) receive +10 and +8 point bonuses
- **Maximum Score**: Capped at 100%

#### Score Interpretation
- **70-100%**: ✅ Highly Relevant - Strong fit for cBrain
- **40-69%**: ⚠️ Moderately Relevant - Potential opportunities
- **0-39%**: ❌ Low Relevance - May not be suitable

### Scoring Breakdown

Each tender shows detailed scoring information:
- **Match Percentage**: Overall relevance score
- **Keywords Found**: Number of matching keywords out of total system keywords
- **Matched Categories**: Which cBrain categories were identified
- **Classification Confidence**: How certain the system is about the categorization

## Database Schema

### TenderSource Model
```
- id: Primary Key
- name: Source name (e.g., "UNDP Kenya")
- url: Source website URL
- active: Whether to include in scans
- favorite: User-marked favorite status
- created_at: Addition timestamp
```

### TenderResult Model
```
- id: Primary Key
- title: Tender title
- link: Direct tender URL
- description: Tender description/summary
- buyer: Procuring organization
- country: Target country/region
- deadline: Tender deadline
- score: Relevance score (0-100)
- keywords_matched: Comma-separated matched keywords
- scoring_breakdown: JSON object with detailed scoring info
- saved: User-saved status
- favorite: User-marked favorite status
- category: Automatic classification
- confidence: Category classification confidence
- source_id: Reference to TenderSource
- created_at: Discovery timestamp
```

### LearnedKeyword Model
```
- id: Primary Key
- keyword: The keyword term
- category: Associated category
- weight: Importance weighting
- created_at: Learning timestamp
```

## Module Overview

### `app/__init__.py`
Flask application factory and initialization

### `app/models.py`
SQLAlchemy database models for Tenders, Sources, and Keywords

### `app/routes.py`
Flask routes and view handlers:
- Scan management
- Tender detail views
- Source CRUD operations
- Favorite/save management

### `app/scoring.py`
Intelligent scoring engine with keyword matching and detailed breakdown

### `app/scraper.py`
Web scraper for discovering tenders from sources

### `app/categorizer.py`
Automatic tender classification into cBrain domains

### `app/learner.py`
Machine learning component for continuous keyword learning

### `app/keywords.py`
Keyword definitions organized by category

### `app/deadlines.py`
Deadline extraction and parsing

### `app/source_bias.py`
Source-specific score adjustments

## API Endpoints

| Method | Route | Purpose |
|--------|-------|---------|
| GET/POST | `/` | Scan dashboard and results |
| GET | `/tender/<id>` | View tender details with scoring |
| POST | `/results/delete` | Clear all scan results |
| GET/POST | `/sources` | Source management |
| POST | `/source/<id>/favorite` | Toggle source favorite |
| POST | `/source/<id>/delete` | Delete source |
| GET | `/favorites` | View favorite tenders |
| GET | `/saved` | View saved tenders |
| POST | `/save/<id>` | Save a tender |
| POST | `/unsave/<id>` | Unsave a tender |
| POST | `/tender/<id>/favorite` | Toggle tender favorite |

## Performance Optimization Tips

1. **Limit Active Sources**: Only enable sources you actively monitor
2. **Regular Cleanup**: Delete old scan results periodically
3. **Batch Operations**: Run scans during off-peak hours
4. **Database Maintenance**: Consider archiving old tenders after 30+ days

## Troubleshooting

### Issue: No scan results appearing
- **Solution**: Ensure at least one source is marked as active
- Check that the source URL is accessible
- Verify the URL contains tender listing pages

### Issue: Slow scan performance
- **Solution**: Reduce the number of active sources
- Check internet connection speed
- Consider limiting scan frequency

### Issue: Scoring seems inconsistent
- **Solution**: Check if keywords are correctly defined in `app/keywords.py`
- Verify source bias settings in `app/source_bias.py`
- Review matched keywords in tender detail view

## Future Enhancements

- [ ] Email notifications for high-scoring tenders
- [ ] Advanced search and filtering
- [ ] Tender opportunity alerts by category
- [ ] Integration with cBrain systems
- [ ] API for third-party integrations
- [ ] Automated bid preparation checklists
- [ ] Tender document analysis
- [ ] Multi-user support with authentication
- [ ] Export functionality (CSV, PDF)
- [ ] Dashboard analytics and metrics

## Configuration

### Customize Keywords

Edit `app/keywords.py` to modify keyword groups:

```python
KEYWORD_GROUPS = {
    "EDMS": [
        "records", "document management", "edms", # Add your keywords
    ],
    # ...
}
```

### Adjust Source Bias

Edit `app/source_bias.py` to modify source score adjustments:

```python
SOURCE_BIAS = {
    "undp": 10,        # +10 bonus for UNDP
    "world bank": 8,   # +8 bonus for World Bank
}
```

## Support & Contribution

For issues, suggestions, or contributions, please contact the cBrain development team.

---

**TenderWatch** - Making tender discovery intelligent and accessible for cBrain's F2 Platform
