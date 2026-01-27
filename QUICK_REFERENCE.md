# 🚀 TenderWatch - Quick Reference

## Start Locally (Choose One)

### Streamlit (Simpler ⭐)
```bash
cd tenderwatch_app
pip install -r requirements.txt
python init_sources.py
streamlit run streamlit_app.py
```
→ Opens at `http://localhost:8501`

### Flask (Original)
```bash
cd tenderwatch_app
pip install -r requirements.txt
python init_sources.py
python run.py
```
→ Opens at `http://localhost:5000`

---

## Deploy Online (Choose One)

### Streamlit Cloud (Easiest ⭐)
1. Push to GitHub
2. Go to streamlit.io/cloud
3. Click "New app" → Select repo
4. Deploy → Get `https://your-app.streamlit.app`

### Railway
1. Go to railway.app
2. Deploy from GitHub
3. Get `https://your-app.railway.app`

### Render
1. Go to render.com
2. New Web Service
3. Get `https://tenderwatch.onrender.com`

---

## Key Files

| File | Purpose |
|------|---------|
| `streamlit_app.py` | Streamlit version (1 file, simple) |
| `run.py` | Flask version entry point |
| `app/routes.py` | Flask routes |
| `app/scraper.py` | Tender scraping logic |
| `app/scoring.py` | Keyword scoring |
| `app/keywords.py` | Keyword definitions |
| `init_sources.py` | Initialize database |

---

## Common Commands

```bash
# Run Streamlit
streamlit run streamlit_app.py

# Run Flask
python run.py

# Initialize database
python init_sources.py

# Install dependencies
pip install -r requirements.txt
```

---

## Documentation

| Guide | Topic |
|-------|-------|
| [README.md](README.md) | Overview & features |
| [START_HERE.md](START_HERE.md) | Quick start guide |
| [STREAMLIT_GUIDE.md](STREAMLIT_GUIDE.md) | Streamlit setup |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Flask deployment |
| [FLASK_VS_STREAMLIT.md](FLASK_VS_STREAMLIT.md) | Compare versions |

---

## URLs

**Local:**
- Streamlit: `http://localhost:8501`
- Flask: `http://localhost:5000`

**Deployed:**
- Streamlit Cloud: `https://[your-app].streamlit.app`
- Railway: `https://[your-app].railway.app`
- Render: `https://[your-app].onrender.com`

---

## Quick Troubleshooting

**App won't start?**
→ Run `pip install -r requirements.txt`

**No tenders?**
→ Run `python init_sources.py` first

**Database error?**
→ Delete `instance/tenderwatch.db` and re-run `init_sources.py`

**Port in use?**
→ Streamlit: Add `--server.port 8502`
→ Flask: Edit `run.py` to change port

---

## Need Help?

1. Check [documentation](README.md)
2. Review [code comments](streamlit_app.py)
3. Compare [Flask vs Streamlit](FLASK_VS_STREAMLIT.md)
4. All code is in one file for Streamlit - just read it!
