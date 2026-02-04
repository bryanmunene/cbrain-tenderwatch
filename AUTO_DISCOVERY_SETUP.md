# Auto-Discovery Setup Guide
**Unlimited tender scanning without manual source management**

## What is Auto-Discovery?

Instead of manually adding tender sources, TenderWatch now automatically searches the **entire web** using Google and Bing APIs to find relevant opportunities. This removes the growth bottleneck and discovers tenders from sites you don't even know about.

### How It Works

```
Search APIs (Google + Bing)
    ↓
14 default keyword searches (e.g., "government tender EDMS")
    ↓
Filter results by relevance
    ↓
Score + categorize with AI
    ↓
Save high-quality tenders to database
```

### Benefits

✅ **No manual source management** - System finds sources automatically  
✅ **Broader coverage** - Discovers tenders from unknown sites  
✅ **Combined quotas** - 133 free searches/day (Google 100 + Bing 33)  
✅ **Smart filtering** - AI scoring eliminates irrelevant results  
✅ **Existing sources preserved** - Manual sources still work as "priority"

---

## Step 1: Get API Keys (15 minutes)

### Google Custom Search API (100 queries/day free)

1. **Get API Key:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create new project (e.g., "TenderWatch")
   - Enable "Custom Search API"
   - Navigate to **APIs & Services → Credentials**
   - Click **Create Credentials → API Key**
   - Copy the key (looks like: `AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXX`)

2. **Create Custom Search Engine (CX):**
   - Go to [Programmable Search Engine](https://programmablesearchengine.google.com/)
   - Click **Add** (Create new search engine)
   - **Sites to search:** Enter `*.gov, *.org, *.com` (searches everything)
   - **Name:** "TenderWatch Global Search"
   - Click **Create**
   - Click **Control Panel** → Copy the **Search Engine ID** (CX)
   - Format: `0123456789abcdefg:hijklmnopqr`

### Bing Search API (1,000 queries/month free)

1. **Get API Key:**
   - Go to [Azure Portal](https://portal.azure.com/) (create account if needed)
   - Click **Create a resource**
   - Search for **"Bing Search v7"**
   - Click **Create**
   - Choose **F0 (Free tier)** pricing
   - Copy the **Key 1** from **Keys and Endpoint** section
   - Format: 32-character hex string

---

## Step 2: Configure TenderWatch

### Flask App

1. **Run migration:**
   ```powershell
   cd tenderwatch_app
   python migrate_discovery.py
   ```

2. **Add API keys:**
   - Open app: `python run.py`
   - Navigate to **Settings → Auto-Discovery**
   - Paste Google API Key, Google CX, and Bing API Key
   - Click **Save Settings**

3. **Test auto-discovery:**
   - Go to **Auto-Discovery** menu (globe icon)
   - Click **"Run Discovery Now"**
   - Wait 30-60 seconds for results

### Streamlit App

1. **Run migration:**
   ```powershell
   cd tenderwatch_app
   python migrate_discovery.py
   ```

2. **Add API keys:**
   - Open app: `streamlit run streamlit_app.py`
   - Click **Settings** in sidebar
   - Expand **"Auto-Discovery (Google + Bing)"** section
   - Enter API keys
   - Toggle **"Enable Auto-Discovery"**

3. **Manual scan:**
   - Click **"Run Scan Now"** button
   - Auto-discovery runs automatically with manual sources

---

## Step 3: Understanding Quotas

### Free Tier Limits

| API    | Free Quota | Resets | Cost After |
|--------|-----------|--------|------------|
| Google | 100/day   | Daily  | $5/1000    |
| Bing   | 1000/month (~33/day) | Monthly | $7/1000 |
| **Combined** | **~133/day** | **Daily** | **Negligible for testing** |

### Quota Management

- **View quota:** Auto-Discovery dashboard shows real-time usage
- **Optimize searches:** Reduce `results_per_query` in settings (default: 10)
- **Custom queries:** Edit search terms to target specific tenders
- **Automatic scheduling:** Auto-discovery runs with scheduled scans

### Cost Estimation

**Conservative usage (10 queries/day):**
- Google: 100/day free → **No cost for 10 queries**
- Bing: 33/day free → **No cost**

**Heavy usage (50 queries/day):**
- Google: 50 within free tier → **No cost**
- Bing: 33 within free tier, 17 paid → **~$0.12/day = $3.60/month**

**For most users:** You'll stay within free tier indefinitely.

---

## Step 4: Customizing Search Queries

### Default Queries (14 total)

```json
[
  "government tender procurement",
  "RFP document management system",
  "RFQ case management software",
  "tender EDMS records management",
  "bid opportunity workflow automation",
  "tender Kenya government",
  "procurement opportunity Africa",
  "RFP international development",
  "tender electronic document management",
  "RFP complaint handling system",
  "procurement business process automation",
  "tender ICT infrastructure",
  "UNDP procurement notice",
  "World Bank tender"
]
```

### Adding Custom Queries

1. Go to **Settings → Auto-Discovery**
2. In **"Custom Search Queries"** field, paste JSON array:
   ```json
   [
     "RFP records management Kenya 2026",
     "tender case management East Africa",
     "government procurement EDMS",
     "bid workflow automation software"
   ]
   ```
3. Click **Save Settings**

### Best Practices

✅ **Specific keywords** - Combine location + tender type + solution  
✅ **Year filters** - Add current year to avoid expired tenders  
✅ **Regional focus** - Target specific countries/regions  
❌ **Avoid generic terms** - "tender" alone wastes quota  
❌ **Don't duplicate** - Each query uses 2 API calls (Google + Bing)

---

## Step 5: Monitoring & Optimization

### Discovery Dashboard (`/discovery`)

**Statistics shown:**
- Total auto-discovered tenders
- Discovery run history (last 20 runs)
- API quota usage (Google + Bing)
- Average execution time
- Error logs

**Manual triggers:**
- "Run Discovery Now" button
- View recent logs with quota consumption
- Monitor quota reset countdown

### Optimizing Performance

**Reduce API calls:**
- Lower `results_per_query` (5 instead of 10)
- Use fewer custom queries
- Schedule discovery less frequently

**Improve quality:**
- Add domain-specific keywords to `keywords.py`
- Adjust scoring thresholds in settings
- Review auto-discovered tenders and refine queries

**Balance manual + auto:**
- Keep high-value sources as manual (UNDP, World Bank)
- Let auto-discovery handle unknown sources
- Auto-discovered tenders labeled with `discovery_method='auto'`

---

## Troubleshooting

### "Auto-discovery not initialized"

**Cause:** API keys not configured  
**Fix:** Add keys in Settings → Auto-Discovery → Save

### "Google API daily quota exceeded"

**Cause:** Used all 100 free queries today  
**Fix:** Wait for midnight UTC reset, or add Bing key to continue

### "Invalid API key" error

**Cause:** Incorrect key format or expired key  
**Fix:** 
- Verify key from Google Cloud Console
- Check for extra spaces when pasting
- Regenerate key if needed

### "No results found"

**Possible causes:**
- Search queries too specific → Use broader terms
- Quota exhausted → Check dashboard
- APIs not returning tender pages → Add custom queries

**Debug steps:**
1. View Discovery Dashboard → Check error logs
2. Test single query manually on Google/Bing
3. Verify API keys are active in respective consoles

### "Slow scans (>60 seconds)"

**Normal behavior:**
- Each query hits 2 APIs (Google + Bing)
- 14 default queries = 28 API calls
- Network latency + filtering + scoring

**Optimization:**
- Reduce `results_per_query` to 5
- Use fewer custom queries (5-7 instead of 14)
- Run discovery less frequently

---

## Advanced Configuration

### Scheduled Auto-Discovery

Auto-discovery runs automatically when:
1. **Scheduled scans enabled** (Settings → Autonomous Scanning)
2. **Auto-discovery enabled** (Settings → Auto-Discovery)
3. Interval configured (e.g., every 60 minutes)

**Disable for manual-only:**
- Uncheck "Enable Auto-Discovery"
- Manual sources still scan on schedule

### API Key Security

**Environment variables (production):**
```powershell
# Windows PowerShell
$env:GOOGLE_API_KEY="AIzaSy..."
$env:GOOGLE_CX="0123456..."
$env:BING_API_KEY="..."

# Linux/Mac
export GOOGLE_API_KEY="AIzaSy..."
export GOOGLE_CX="0123456..."
export BING_API_KEY="..."
```

**Load in app (add to `__init__.py`):**
```python
import os
if not settings.google_api_key:
    settings.google_api_key = os.getenv('GOOGLE_API_KEY', '')
if not settings.google_cx:
    settings.google_cx = os.getenv('GOOGLE_CX', '')
if not settings.bing_api_key:
    settings.bing_api_key = os.getenv('BING_API_KEY', '')
```

### Hybrid Source Strategy

**Best approach for growth:**

1. **Manual sources (priority):**
   - Major procurement sites (UNDP, World Bank, GEF)
   - High-value specific sources
   - Sources with structured data

2. **Auto-discovery:**
   - Unknown/emerging tender sites
   - Regional government portals
   - Private sector opportunities

3. **Promote strategy:**
   - Monitor auto-discovered tenders
   - Add successful sources manually for priority
   - Disable low-quality sources

---

## FAQ

**Q: Will auto-discovery replace manual sources?**  
A: No. Manual sources remain as "priority sources" and get scanned first. Auto-discovery supplements them.

**Q: How much does it cost?**  
A: Free for typical usage (<100 Google + 33 Bing queries/day). Heavy users: ~$5-10/month.

**Q: Can I use only one API?**  
A: Yes. Leave the other API key blank. You'll get results from just Google or Bing.

**Q: How often should I run auto-discovery?**  
A: 2-4 times/day is optimal. More frequent = wasted quota (sites don't update hourly).

**Q: Will I get duplicate tenders?**  
A: No. System checks `link` uniqueness before adding. Duplicates from different sources are skipped.

**Q: Can I filter auto-discovered tenders?**  
A: Yes. Use `discovery_method='auto'` in filters. Settings → Min score threshold filters low-quality results.

**Q: What if I exceed quota?**  
A: Discovery stops for the day. No cost incurred. Resumes next day after reset.

---

## Next Steps

✅ Run `python migrate_discovery.py`  
✅ Get Google + Bing API keys  
✅ Configure in Settings → Auto-Discovery  
✅ Test with "Run Discovery Now"  
✅ Monitor quota in Discovery Dashboard  
✅ Customize search queries for your needs

**Need help?** Check Discovery Dashboard error logs or review API console quotas.
