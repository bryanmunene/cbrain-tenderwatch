# 📱 Access TenderWatch on Your Phone

## Quick Start (Local Network)

### Step 1: Restart the Server
The app has been configured to accept connections from your local network. Restart it:

```bash
cd tenderwatch_app
python run.py
```

You should see:
```
* Running on http://0.0.0.0:5000
* Running on http://192.168.1.59:5000
```

### Step 2: Connect from Your Phone

**Make sure your phone is on the same WiFi network as your computer!**

Then open your phone's browser and go to:

```
http://192.168.1.59:5000
```

That's it! You can now use TenderWatch from your phone. 📱

---

## 📲 Options for Remote Access

### Option 1: Local Network (Recommended for Home Use)
✅ **Pros**: Free, fast, secure
❌ **Cons**: Only works on same WiFi

**Your IP**: `192.168.1.59:5000`

### Option 2: Deploy Online (⭐ Best for Anywhere Access)

**Why this is easier:** No tunneling software, permanent URL, always accessible.

**Quick Deploy (Choose One - All Free Tiers):**

#### **Railway** (Easiest - 1 Click Deploy)
1. Go to https://railway.app and sign in with GitHub
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your `cbrain_tenderwatch` repo
4. Railway auto-deploys in ~2 minutes
5. Get URL: `https://your-app.railway.app`

✅ **Pros**: Instant setup, auto-deploy, free $5/month credit
❌ **Cons**: Credit runs out eventually (upgrade or use Render)

#### **Render** (Free Forever)
1. Go to https://render.com and sign in with GitHub
2. New → Web Service → Connect your repo
3. Configure: Root dir = `tenderwatch_app`, Build = `pip install -r requirements.txt && python init_sources.py`
4. Start command: `gunicorn run:app --bind 0.0.0.0:$PORT`
5. Deploy and get: `https://tenderwatch.onrender.com`

✅ **Pros**: 100% free forever, auto-SSL, auto-deploy
❌ **Cons**: Sleeps after 15min inactivity (wakes instantly when accessed)

#### **Heroku** (Classic Platform)
```bash
# Install Heroku CLI from https://devcenter.heroku.com/articles/heroku-cli
heroku login
cd cbrain_tenderwatch
heroku create tenderwatch-app
git push heroku main
heroku run python tenderwatch_app/init_sources.py
heroku open
```

✅ **Pros**: Mature platform, reliable, lots of addons
❌ **Cons**: 550 free hours/month (upgrade for 24/7)

**📖 Full deployment guide: See [DEPLOYMENT.md](DEPLOYMENT.md)**

#### **PythonAnywhere** (Free tier available)
- Upload code to PythonAnywhere
- Configure WSGI file
- Access via: `yourname.pythonanywhere.com`

#### **Railway.app** (Free tier)
- Connect GitHub repo
- Auto-deploys on push
- Provides HTTPS URL

#### **Render** (Free tier)
- Connect GitHub repo
- Configure as Web Service
- Automatic HTTPS

### Option 4: Progressive Web App (PWA)

Make TenderWatch installable on your phone:

Add to `base.html` in `<head>`:
```html
<link rel="manifest" href="/static/manifest.json">
<meta name="theme-color" content="#1e3a8a">
<meta name="mobile-web-app-capable" content="yes">
```

Create `/static/manifest.json`:
```json
{
  "name": "TenderWatch",
  "short_name": "TenderWatch",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#1e3a8a",
  "icons": [
    {
      "src": "/static/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    }
  ]
}
```

Then you can "Add to Home Screen" from your phone's browser!

---

## 🔒 Security Considerations

### For Local Network Access
- Already secure (only accessible on your WiFi)
- No passwords needed if on trusted network
- Consider adding authentication if others share your WiFi

### For Internet Access
If deploying publicly, add authentication:

1. **Basic Auth** (Quick):
```python
from flask_httpauth import HTTPBasicAuth
auth = HTTPBasicAuth()

@auth.verify_password
def verify_password(username, password):
    if username == "admin" and password == "your_password":
        return True
    return False

@main.route("/")
@auth.login_required
def dashboard():
    # ... existing code
```

2. **User System** (Comprehensive):
- Use Flask-Login
- Add user registration/login
- Store hashed passwords
- Session management

---

## 🎯 Recommended Setup

**For Home Use (Same WiFi)**:
- ✅ Use local network access (192.168.1.59:5000)
- ✅ Fast, free, secure
- ✅ Works on phone, tablet, any device on your WiFi

**For Anywhere Access (Internet)**:
- ✅ **Deploy to Railway or Render** (easiest, permanent)
- ✅ Get HTTPS URL: `https://your-app.railway.app`
- ✅ Access from anywhere: home, office, traveling
- ✅ No need to keep your PC running
- ✅ Free tiers available

**For Team/Production Use**:
- Deploy to cloud platform (Railway/Render/Heroku)
- Add authentication if needed
- Use environment variables for sensitive data
- Set up monitoring

---

## 📱 Mobile-Friendly Tips

The UI is already responsive, but for best mobile experience:

1. **Add Bookmark**: Save the URL to your home screen
2. **Portrait Mode**: Works best in portrait orientation
3. **Notifications**: Desktop notifications won't work on mobile (email works!)
4. **Network**: Ensure stable WiFi/data connection

---

## 🐛 Troubleshooting

**Can't connect from phone?**
- ✓ Both devices on same WiFi?
- ✓ Firewall blocking port 5000?
- ✓ Using correct IP (192.168.1.59)?
- ✓ Server running and showing "0.0.0.0:5000"?

**Windows Firewall**:
```powershell
New-NetFirewallRule -DisplayName "TenderWatch" -Direction Inbound -Port 5000 -Protocol TCP -Action Allow
```

**Connection refused?**
- Check server is running with `host='0.0.0.0'`
- Try disabling firewall temporarily to test

**Slow on phone?**
- Normal - local network can be slower than localhost
- Consider caching strategies for production

---

## ✨ Current Status

✅ **Configured**: Server accepts network connections
✅ **Your Local URL**: `http://192.168.1.59:5000`
✅ **Mobile-Responsive**: UI works on all screen sizes

**To access now:**
1. Restart server: `python run.py`
2. Open phone browser
3. Go to: `http://192.168.1.59:5000`
4. Enjoy TenderWatch on mobile! 📱

---

**Questions?** Try the connection and let me know if you need help with any of the deployment options!
