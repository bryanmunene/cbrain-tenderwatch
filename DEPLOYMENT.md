# TenderWatch Deployment Guide

This guide covers **easy, one-click deployment** options for TenderWatch.

> 💡 **Want your app always live?** See [KEEP_ALIVE_SETUP.md](KEEP_ALIVE_SETUP.md) for free solutions using GitHub Actions + UptimeRobot

## 🚀 Quick Deploy (Choose One - All Free Tiers Available)

### ⭐ Option 1: Railway (Easiest - Recommended)

**Why Railway:** One-click deploy, automatic HTTPS, built-in database, free $5/month credit.

1. **Fork this repository** on GitHub (if not already done)

2. **Go to [Railway.app](https://railway.app)** and sign in with GitHub

3. **Click "New Project" → "Deploy from GitHub repo"**

4. **Select your forked `cbrain_tenderwatch` repository**

5. **Railway auto-detects Python** and uses the `Procfile`

6. **Add environment variables** in Railway dashboard:
   - No variables needed - app works out of the box!
   - (Optional) Add `SECRET_KEY` for production security

7. **Click Deploy** - Railway will:
   - Install dependencies from `requirements.txt`
   - Run `init_sources.py` automatically (if configured)
   - Start the app with `gunicorn`
   - Give you a public URL like `https://your-app.railway.app`

**That's it!** Your app is live in ~2 minutes.

**Railway Docs:** https://docs.railway.app/deploy/deployments

---

### ⭐ Option 2: Render (Free Tier Forever)

**Why Render:** 100% free tier forever, auto-deploys from GitHub, simple setup.

1. **Go to [Render.com](https://render.com)** and sign up with GitHub

2. **Click "New +" → "Web Service"**

3. **Connect your GitHub repository**

4. **Configure the service:**
   - **Name:** tenderwatch
   - **Region:** Choose closest to you
   - **Branch:** main
   - **Root Directory:** `tenderwatch_app`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt && python init_sources.py`
   - **Start Command:** `gunicorn run:app --bind 0.0.0.0:$PORT`

5. **Click "Create Web Service"**

6. **Wait ~5 minutes** - Render will deploy and give you a URL like `https://tenderwatch.onrender.com`

**Note:** Free tier sleeps after 15 min of inactivity (wakes up automatically when accessed).

**Render Docs:** https://render.com/docs/web-services

---

### ⭐ Option 3: Heroku (Classic, Reliable)

**Why Heroku:** Most mature platform, large community, lots of addons.

1. **Install Heroku CLI:** https://devcenter.heroku.com/articles/heroku-cli

2. **Login to Heroku:**
   ```bash
   heroku login
   ```

3. **Create new app:**
   ```bash
   cd cbrain_tenderwatch
   heroku create your-tenderwatch-app
   ```

4. **Deploy:**
   ```bash
   git push heroku main
   ```

5. **Initialize database:**
   ```bash
   heroku run python tenderwatch_app/init_sources.py
   ```

6. **Open app:**
   ```bash
   heroku open
   ```

**Heroku Docs:** https://devcenter.heroku.com/articles/getting-started-with-python

---

## 🔧 Local Development

### Setup in 3 Steps

1. **Navigate to app directory**
   ```bash
   cd tenderwatch_app
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Initialize and run**
   ```bash
   python init_sources.py
   python run.py
   ```

   App available at: `http://localhost:5000`

---

## 🌐 Production Deployment (Advanced)

#### 1. Install Gunicorn
```bash
pip install gunicorn
```

#### 2. Create Gunicorn config file (`wsgi.conf`)
```python
import multiprocessing

bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
timeout = 30
keepalive = 2
```

#### 3. Create systemd service file (`/etc/systemd/system/tenderwatch.service`)
```ini
[Unit]
Description=TenderWatch Application
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/tenderwatch_app
ExecStart=/path/to/tenderwatch_app/venv/bin/gunicorn \
    --config wsgi.conf \
    --bind 0.0.0.0:8000 \
    run:app

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```


### If You Need Custom Domain (All Options Support This)

**Railway:** Settings → Domains → Add custom domain
**Render:** Settings → Custom Domain → Add yours
**Heroku:** Settings → Domains → Add custom domain

All platforms provide free SSL certificates automatically!

---

## 🛠️ Troubleshooting

### App Won't Start
- Check build logs in your platform dashboard
- Verify `requirements.txt` includes all dependencies
- Ensure `Procfile` points to correct file

### Database Issues
- Railway/Render: Database persists automatically
- If needed, re-run: `python init_sources.py`

### Slow Performance
- **Railway:** Upgrade beyond free tier
- **Render:** Free tier sleeps - upgrade to keep awake 24/7
- **Heroku:** Use hobby dyno ($7/month) for better performance

---

## 📊 Platform Comparison

| Platform | Free Tier | Auto-Deploy | Database | SSL | Best For |
|----------|-----------|-------------|----------|-----|----------|
| **Railway** | $5/mo credit | ✅ | ✅ Included | ✅ | Easiest setup |
| **Render** | ✅ Forever | ✅ | ✅ Included | ✅ | Long-term free |
| **Heroku** | 550 hrs/mo | ✅ | ⚠️ Addon | ✅ | Enterprise scale |

**Recommendation:** Start with **Railway** or **Render** for instant deployment!

---

## 🔒 Production Security Checklist

- [ ] Set strong `SECRET_KEY` environment variable
- [ ] Enable HTTPS (automatic on all platforms)
- [ ] Disable Flask debug mode (`FLASK_ENV=production`)
- [ ] Review tender source URLs for validity
- [ ] Set up monitoring/alerts (optional)

---

## 📁 Database Backup

All platforms auto-backup your database, but you can manually backup:

```bash
# Download database file from deployment
scp your-server:/path/to/instance/tenderwatch.db ./backup_$(date +%Y%m%d).db
```

---

## 🎓 Advanced: Self-Hosted VPS (Optional)

Only if you need full control on your own server:

### Using Gunicorn + Nginx

### Reset Database
```bash
# Remove old database
rm instance/tenderwatch.db

# Reinitialize
python init_sources.py
```

### Export Results
```python
from app import create_app
from app.models import TenderResult
import csv

app = create_app()
with app.app_context():
    results = TenderResult.query.all()
    
    with open('export.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Title', 'Buyer', 'Country', 'Score', 'Deadline', 'Link'])
        for r in results:
            writer.writerow([r.title, r.buyer, r.country, r.score, r.deadline, r.link])
```

## Performance Optimization

### 1. Database Indexing
```python
# In app/models.py - add indexes for common queries
class TenderResult(db.Model):
    __table_args__ = (
        db.Index('idx_score', 'score'),
        db.Index('idx_created_at', 'created_at'),
        db.Index('idx_favorite', 'favorite'),
    )
```

### 2. Caching (Redis)
```python
# Add to requirements.txt
redis
flask-caching

# In app/__init__.py
from flask_caching import Cache

cache = Cache(app, config={'CACHE_TYPE': 'redis'})
```

### 3. Scheduled Scans (Celery)
```python
# In app/__init__.py
from celery import Celery

celery = Celery(app.name, broker='redis://localhost:6379')

@celery.task
def scheduled_scan():
    from app.scraper import run_scan
    run_scan()
```

## Monitoring & Logging

### 1. Application Logging
```python
# In run.py
import logging

logging.basicConfig(
    filename='logs/tenderwatch.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### 2. Health Check Endpoint
```python
# In app/routes.py
@main.route('/health')
def health():
    return {'status': 'healthy'}, 200
```

### 3. Monitor with New Relic
```python
# Install agent
pip install newrelic

# Add to Procfile (Heroku)
web: newrelic-admin run-program gunicorn run:app
```

## Scaling Considerations

- **Multiple Workers**: Use Gunicorn with multiple worker processes
- **Caching**: Implement Redis for session and query caching
- **Database**: Consider PostgreSQL for production instead of SQLite
- **Queue System**: Use Celery + Redis for async scan operations
- **Load Balancing**: Use nginx or AWS ELB for traffic distribution

## Security Checklist

- [ ] Change `SECRET_KEY` in production
- [ ] Enable HTTPS/SSL
- [ ] Set `FLASK_ENV=production`
- [ ] Implement rate limiting
- [ ] Add authentication/authorization
- [ ] Validate all user inputs
- [ ] Keep dependencies updated
- [ ] Use environment variables for secrets
- [ ] Implement CORS properly
- [ ] Add Web Application Firewall (WAF)

## Troubleshooting

### Application won't start
```bash
# Check logs
journalctl -u tenderwatch -n 50

# Verify database
python -c "from app import create_app; app = create_app()"
```

### High memory usage
```bash
# Limit Gunicorn workers
gunicorn --workers 2 run:app

# Archive old scan results
# Add periodic cleanup task
```

### Slow scans
```bash
# Reduce source URLs
# Implement scan queuing
# Use async workers
```

## Maintenance

### Weekly Tasks
- Monitor application logs
- Check disk space
- Verify backups

### Monthly Tasks
- Update dependencies: `pip install --upgrade -r requirements.txt`
- Archive old scan results
- Review performance metrics

### Quarterly Tasks
- Security audit
- Dependency vulnerability scan
- Performance optimization review

## Support

For deployment issues or questions, contact the DevOps team.

---

**TenderWatch Deployment Guide** - v1.0
