# Keep TenderWatch Always Live - Setup Guide

Since you have a GitHub repository, here are **free solutions** to keep your app running 24/7.

---

## ✅ Solution 1: GitHub Actions Auto-Scanner (Already Configured!)

**What it does:**
- Runs tender scanning automatically every hour
- No server needed - GitHub runs it for free
- Saves results to database
- Your UI just displays the pre-scanned data

**Status:** ✅ Workflows already added to `.github/workflows/`
- `auto-scan.yml` - Scans tenders every hour
- `keep-alive.yml` - Pings your deployed app every 5 minutes

### Configuration Steps:

#### 1. Enable GitHub Actions
```bash
# Your workflows are already in .github/workflows/
# Just commit and push:
git add .github/workflows/
git commit -m "Add auto-scan and keep-alive workflows"
git push
```

#### 2. Set Up Repository Variables
Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **Variables**

Add these variables:

| Variable Name | Value | Description |
|--------------|-------|-------------|
| `STREAMLIT_URL` | `https://your-app.streamlit.app` | Your Streamlit deployment URL |
| `FLASK_URL` | `https://your-app.railway.app` | Your Flask deployment URL (if using) |
| `API_URL` | Same as Flask URL | For health check endpoint |

**Leave blank** any URLs you're not using.

#### 3. Test the Workflow
- Go to **Actions** tab in GitHub
- Click "Auto Scan Tenders" → **Run workflow**
- Wait 2-3 minutes, check the logs
- Should see: "✅ Scan complete! Found X new tenders"

---

## ✅ Solution 2: UptimeRobot (Free Tier)

**What it does:**
- Pings your deployed app every 5 minutes
- Prevents free-tier platforms from sleeping
- Monitors uptime and alerts you if app goes down

### Setup Steps:

#### 1. Sign Up
- Go to [uptimerobot.com](https://uptimerobot.com)
- Create free account (50 monitors included)

#### 2. Create Monitor
```
Monitor Type: HTTP(s)
Friendly Name: TenderWatch Streamlit
URL: https://your-app.streamlit.app
Monitoring Interval: 5 minutes
```

#### 3. Add Second Monitor (Optional - for Flask)
```
Monitor Type: HTTP(s)
Friendly Name: TenderWatch Flask
URL: https://your-app.railway.app
Monitoring Interval: 5 minutes
```

#### 4. Enable Notifications
- Add your email in Alert Contacts
- Get notified if app goes down

**Result:** App stays warm, loads instantly for users

---

## ✅ Solution 3: Hybrid Approach (Recommended)

Combine both for maximum uptime:

### Architecture:
```
GitHub Actions (every hour)
   ↓
   Scans tenders → Updates database
   ↓
UptimeRobot (every 5 min)
   ↓
   Pings your UI → Keeps it awake
   ↓
Users visit → See fresh data instantly
```

### Benefits:
- ✅ **Always has fresh data** (hourly scans)
- ✅ **UI never sleeps** (5-min pings)
- ✅ **100% free** (no paid hosting needed)
- ✅ **Monitoring included** (uptime alerts)

---

## 🔧 Advanced: Configure Scan Frequency

Edit `.github/workflows/auto-scan.yml`:

```yaml
on:
  schedule:
    # Every hour
    - cron: '0 * * * *'
    
    # Every 30 minutes (more frequent)
    # - cron: '*/30 * * * *'
    
    # Every 6 hours (less frequent, saves GitHub Actions minutes)
    # - cron: '0 */6 * * *'
    
    # Business hours only (9 AM - 5 PM UTC, Mon-Fri)
    # - cron: '0 9-17 * * 1-5'
```

---

## 📊 Monitoring Your Setup

### Check GitHub Actions Status:
1. Go to repo → **Actions** tab
2. See recent workflow runs
3. Click any run for detailed logs

### Check UptimeRobot Status:
1. Login to uptimerobot.com
2. Dashboard shows uptime percentage
3. View response times and downtime history

### App Health Check:
```powershell
# Test your app is responding
curl https://your-app.streamlit.app

# Test API endpoint (Flask only)
curl https://your-app.railway.app/api/source-status
```

---

## 💰 Cost Comparison

| Solution | Cost | Uptime | Data Freshness |
|----------|------|--------|----------------|
| **GitHub Actions + UptimeRobot** | **$0/month** | ~95% | Hourly |
| Railway Hobby | $5/month | 99.9% | Real-time |
| Render Starter | $7/month | 99.9% | Real-time |
| Streamlit Paid | $20/month | 99.9% | Real-time |
| DigitalOcean VPS | $6/month | 99.99% | Real-time |

**Recommendation:** Start with the free option, upgrade only if you need:
- Real-time scanning (not hourly batches)
- >95% uptime guarantee
- Custom domain/branding
- Higher traffic capacity

---

## 🚨 Troubleshooting

### "GitHub Actions workflow failed"
- Check **Actions** tab for error logs
- Common issue: Database permission errors
- Fix: Ensure `instance/` directory exists in repo

### "UptimeRobot shows app down"
- Your free tier might have exhausted monthly credits
- Streamlit Cloud free tier: 1GB bandwidth/month limit
- Railway free tier: $5 execution credit/month
- **Solution:** Upgrade to paid tier or reduce ping frequency

### "Scan runs but no new tenders"
- All sources might have returned no new results (normal)
- Check logs: Should show "Found 0 new tenders"
- Verify sources are active: `TenderSource.active = True` in DB

### "Database not updating"
- GitHub Actions can't push back to repo by default
- Alternative: Upload DB as artifact (already configured)
- Download latest DB from **Actions** → **Artifacts**

---

## 🎯 Quick Start Checklist

- [ ] Commit `.github/workflows/` to your repo
- [ ] Push to GitHub
- [ ] Add STREAMLIT_URL/FLASK_URL variables in GitHub Settings
- [ ] Test "Auto Scan Tenders" workflow manually
- [ ] Sign up for UptimeRobot
- [ ] Create HTTP monitor with your app URL
- [ ] Set interval to 5 minutes
- [ ] Wait 1 hour, verify scan ran successfully
- [ ] Check app loads instantly (not sleeping)

**Done!** Your app is now always live with fresh data, completely free. 🎉
