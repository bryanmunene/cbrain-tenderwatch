# TenderWatch Quick Start Guide

Get TenderWatch up and running in 5 minutes!

## Prerequisites

- Python 3.8 or higher
- pip (comes with Python)

## Installation (Windows)

### Step 1: Navigate to Project Directory
```bash
cd c:\Users\BMK\Desktop\cbrain_tenderwatch\tenderwatch_app
```

### Step 2: Create Virtual Environment
```bash
python -m venv venv
venv\Scripts\activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Initialize Database
```bash
python init_sources.py
```

You should see:
```
✓ Added 8 tender sources
  - 4 Kenya-specific sources
  - 4 Global sources
```

### Step 5: Start the Application
```bash
python run.py
```

The app will start on: **http://localhost:5000**

## First Steps

1. **Open your browser** to `http://localhost:5000`

2. **Run your first scan**:
   - Click the **"Run Scan"** button
   - Wait for the scan to complete (30-60 seconds)

3. **View results**:
   - Tenders are sorted by relevance score (highest first)
   - Click on any tender title to see details

4. **Add favorite tenders**:
   - Click the ⭐ star icon to mark tenders
   - View all favorites in the **"Favorites"** menu

5. **Manage sources**:
   - Go to **"Sources"** menu
   - Add new tender sources or manage existing ones

## Common Tasks

### Add a Custom Tender Source

1. Go to **Sources** menu
2. Enter source name: `My Organization Tenders`
3. Enter URL: `https://example.com/tenders`
4. Click **Add Source**
5. Source will be included in next scan

### View Tender Details

1. Click on a tender title
2. See detailed information:
   - **Scoring Breakdown**: Why it received that score
   - **Matched Keywords**: Which keywords triggered the match
   - **Direct Link**: Click to visit the original tender
   - **Save/Favorite**: Options to save for later

### Sort Results

On the Scan Results page:
- **By Score**: Most relevant tenders first
- **By Newest**: Recently discovered tenders first
- **By Deadline**: Earliest deadlines first

### Save Tenders for Later

- Click the **bookmark** icon on a tender
- Go to **Saved** menu to view all saved tenders
- Saved tenders persist in the database

## Understanding Scores

Tenders are scored 0-100% based on relevance:

- **70-100%** ✅ Highly Relevant (Strong fit for cBrain)
- **40-69%** ⚠️ Moderately Relevant (Worth reviewing)
- **0-39%** ❌ Low Relevance (May not be suitable)

**Why?** The system searches for keywords related to:
- Records/Document Management
- Case Management
- Software/Technology Solutions
- Procurement & Consulting
- Infrastructure

## Tips & Tricks

### 🚀 Maximize Efficiency

1. **Mark favorite sources**: In the Sources page, star sources you check frequently
2. **Regular scans**: Schedule regular scans to catch new opportunities
3. **Save interesting tenders**: Use the Save feature to build a portfolio
4. **Check deadlines**: Sort by deadline to prioritize opportunities

### 🎯 Better Results

1. **Add relevant sources**: Include regional procurement boards and international agencies
2. **Review scoring**: Understand why each tender received its score
3. **Track patterns**: Note which sources have the best-fit opportunities

### 🛠️ Customize

To modify keyword matching:
- Edit `app/keywords.py` to add industry-specific keywords
- Adjust source scores in `app/source_bias.py`
- Modify categories in `app/categorizer.py`

## Troubleshooting

### Port Already in Use
If port 5000 is busy:
```bash
python run.py --port 5001
```

### No Results from Scans
- Check that sources are **active** (green status in Sources page)
- Verify source URLs are accessible
- Ensure keywords match tender descriptions

### Database Errors
Reset the database:
```bash
# Delete database file
rm instance/tenderwatch.db

# Reinitialize
python init_sources.py
python run.py
```

## Keyboard Shortcuts

- `Ctrl+L` - Focus on scan results table
- `Ctrl+M` - Go to main scan page
- `Ctrl+S` - Save current tender (on detail page)

## Next Steps

1. **Add more sources**: Go to Sources and add procurement boards specific to your region
2. **Customize keywords**: Edit keywords.py to match your business domain
3. **Set up automation**: Use a scheduler to run scans daily
4. **Deploy to cloud**: Follow [DEPLOYMENT.md](DEPLOYMENT.md) for production setup

## Getting Help

### Check Logs
```bash
# View recent application activity
tail -f logs/tenderwatch.log
```

### Database Info
```bash
# Check stored tenders
sqlite3 instance/tenderwatch.db "SELECT COUNT(*) FROM tender_result;"
```

## Performance Notes

- First scan may take 30-60 seconds as sources are fetched
- Subsequent scans are faster due to caching
- Database is SQLite (suitable for up to 100k+ records)
- For larger deployments, upgrade to PostgreSQL

---

**Now you're ready!** 🚀

Run `python run.py` and start finding tender opportunities!
