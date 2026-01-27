# 🚀 TenderWatch - Streamlit Quick Start

## ⚡ Run Locally (3 Steps)

### 1. Install Dependencies
```bash
cd tenderwatch_app
pip install -r requirements.txt
```

### 2. Initialize Database
```bash
python init_sources.py
```

### 3. Run Streamlit App
```bash
streamlit run streamlit_app.py
```

**Your app opens automatically at:** `http://localhost:8501`

---

## 🌐 Deploy Online (1-Click - Even Easier Than Flask!)

### ⭐ Streamlit Cloud (Recommended - Free Forever)

**Why Streamlit Cloud:** Built specifically for Streamlit apps, 100% free, instant deployment.

1. **Push to GitHub:**
   ```bash
   git add .
   git commit -m "Convert to Streamlit"
   git push
   ```

2. **Go to [streamlit.io/cloud](https://streamlit.io/cloud)** and sign in with GitHub

3. **Click "New app"**

4. **Configure:**
   - Repository: `your-username/cbrain_tenderwatch`
   - Branch: `main`
   - Main file path: `tenderwatch_app/streamlit_app.py`

5. **Click "Deploy"**

6. **Done!** Get URL: `https://your-app.streamlit.app`

**That's it!** No configuration files, no build commands, no complex setup.

---

### Alternative: Railway (Also Works with Streamlit)

1. **Go to [railway.app](https://railway.app)** → Sign in with GitHub

2. **New Project** → Deploy from GitHub → Select repo

3. **Add Start Command:**
   ```
   streamlit run tenderwatch_app/streamlit_app.py --server.port=$PORT
   ```

4. **Deploy** → Get URL: `https://your-app.railway.app`

---

## 🎯 What Changed (Flask → Streamlit)

### Before (Flask):
- ❌ Multiple files: routes.py, templates/*.html, static/*, __init__.py
- ❌ Need to learn: Jinja2, HTML, CSS, Flask routing
- ❌ 1000+ lines across many files
- ❌ Complex deployment configuration

### After (Streamlit):
- ✅ **One file:** `streamlit_app.py` (600 lines, everything included)
- ✅ **Pure Python:** No HTML, CSS, or templates
- ✅ **Auto UI:** Widgets generated automatically
- ✅ **1-click deploy:** Built-in Streamlit Cloud hosting
- ✅ **Live reload:** Changes appear instantly

---

## 📱 Features

All original features preserved:
- ✅ Dashboard with statistics
- ✅ Tender scanning & results
- ✅ Source management (add/edit/delete)
- ✅ Favorites & saved tenders
- ✅ Filtering & sorting
- ✅ Scoring breakdown
- ✅ cBrain branding (blue/teal theme)
- ✅ Settings configuration

**Plus new benefits:**
- 🎨 Cleaner, more modern UI
- 📊 Built-in charts and metrics
- 🔄 Instant page updates
- 📱 Better mobile experience
- ⚡ Faster development

---

## 🆚 Flask vs Streamlit: Side-by-Side

| Feature | Flask (Old) | Streamlit (New) |
|---------|-------------|-----------------|
| **Setup** | 5+ files | 1 file |
| **Code Complexity** | High | Low |
| **HTML/CSS Needed** | Yes | No |
| **Deployment** | Manual config | 1-click |
| **Learning Curve** | Steep | Gentle |
| **Dev Speed** | Slower | Faster |
| **Live Reload** | Manual | Automatic |
| **Built-in Widgets** | None | Many |

---

## 🔄 Switching Between Versions

**To use Streamlit (new):**
```bash
streamlit run streamlit_app.py
```

**To use Flask (old):**
```bash
python run.py
```

Both work! Choose what you prefer.

---

## 📚 Learn More

- **Streamlit Docs:** https://docs.streamlit.io
- **Deployment Guide:** https://docs.streamlit.io/streamlit-community-cloud
- **Gallery:** https://streamlit.io/gallery (see what's possible)

---

## 💡 Next Steps

1. **Test locally:** Run `streamlit run streamlit_app.py`
2. **Deploy:** Push to GitHub → Deploy on Streamlit Cloud
3. **Customize:** Edit `streamlit_app.py` (it's just Python!)
4. **Share:** Send your `https://your-app.streamlit.app` URL to anyone

**Questions?** The entire app is in one file - just read `streamlit_app.py`!
