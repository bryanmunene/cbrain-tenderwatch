# TenderWatch Features Overview

## 🎯 Main Features

### 1. **Tender Opportunity Scanning**

**What it does:**
- Automatically scans multiple tender sources simultaneously
- Discovers new procurement opportunities
- Stores results in database for analysis

**How to use:**
1. Go to the Scan page (main menu)
2. Click "Run Scan" button
3. Wait for scan to complete (30-60 seconds)
4. View results sorted by relevance score

**Key benefits:**
- Discovers opportunities you might miss manually
- Covers both Kenya and global sources
- Regular scanning keeps database updated

---

### 2. **Intelligent Scoring System**

**What it does:**
- Analyzes tenders to determine relevance to cBrain
- Scores on scale of 0-100%
- Considers keyword matches and source quality

**Score Breakdown:**
```
Technical Process:
1. Extract tender text
2. Search for domain-specific keywords
3. Calculate match percentage
4. Apply source bonuses (premium sources get +5 to +10)
5. Cap at 100%
```

**Score Interpretation:**
- 🟢 **70-100%**: Highly Relevant - Strong fit
- 🟡 **40-69%**: Moderately Relevant - Worth reviewing
- 🔴 **0-39%**: Low Relevance - Probably not suitable

**Why certain tenders score high:**
- Contain keywords like: "document management", "platform", "software", "bid", "workflow"
- Come from trusted sources (UNDP, World Bank)
- Match cBrain's core business domains

---

### 3. **Tender Details & Scoring Explanation**

**What it shows:**
Click on any tender to see:

#### **Main Information**
- Complete tender title
- Procuring organization (buyer)
- Target country/region
- Submission deadline
- Original source

#### **Scoring Details**
- Overall relevance score (large display)
- Total keywords matched
- Specific keywords found
- Categories that matched
- Classification confidence level

#### **Content**
- Full tender description (when available)
- All matched keywords in badge format
- Direct, clickable link to original tender source

**Example:**
```
Tender: "Digital Document Management System Implementation"

Score: 85% (Highly Relevant)

Scoring Breakdown:
- Total Keywords in System: 45
- Keywords Matched: 12
- Match Percentage: 85%

Matched Groups:
- EDMS/Records: 5 keywords (document, management, system, digital, records)
- ICT/Software: 4 keywords (implementation, software, platform, system)
- Procurement: 3 keywords (bid, procurement, tender)

Why This Score:
The tender heavily emphasizes document management and digital systems,
which align perfectly with cBrain's EDMS platform.
```

---

### 4. **Save & Favorite Tenders**

**Saving Tenders:**
- Click bookmark icon to save
- Saved tenders accessible from "Saved" menu
- Great for building a portfolio

**Favorite Tenders:**
- Click star icon to add to favorites
- Dedicated "Favorites" view
- Quick access from main menu
- Starred tenders persist in database

**Use Cases:**
- Save interesting opportunities for later review
- Star most promising tenders
- Organize by relevance level

---

### 5. **Tender Source Management**

**Add Custom Sources:**
1. Go to "Sources" menu
2. Enter source name and URL
3. Click "Add Source"
4. Source automatically included in scans

**Manage Sources:**
- **Active/Inactive**: Toggle whether source is scanned
- **Favorite**: Mark frequently-used sources
- **Delete**: Remove sources no longer needed
- **Direct Links**: Visit source website with one click

**Recommended Sources Include:**
```
Kenya-Specific:
- UNDP Kenya
- World Bank Kenya
- USAID Kenya
- African Development Bank

Global:
- UNDB Global
- Global Environment Facility
- International Finance Corporation
- UN Office for Project Services
```

**Source Quality:**
- Sources with history of relevant tenders get bonus points
- Premium sources (UNDP, World Bank) score +8 to +10 points
- Helps surface opportunities from trusted organizations

---

### 6. **Direct Source Access**

**What it means:**
Every tender provides:
- ✅ Direct, clickable link to original tender
- ✅ Opens in new browser tab
- ✅ No intermediary navigation
- ✅ Quick access to full tender details on source website

**Usage:**
1. View a tender (click title or eye icon)
2. Scroll to "Direct Access Link" section
3. Click "Open Tender Opportunity" button
4. Source website opens in new tab
5. Review full tender details and apply directly

**Benefits:**
- Instant access to original information
- Verify relevance personally
- Apply directly from source
- No data loss or misinterpretation

---

### 7. **Advanced Filtering & Sorting**

**Sort Options:**
- **By Score**: Highest relevance first (default)
- **By Newest**: Recently discovered tenders
- **By Deadline**: Earliest deadlines first

**Filter Options:**
- View all tenders
- View saved tenders only
- View favorite tenders only

**Search Capabilities:**
- Future: Search by keyword, date range, country
- Future: Advanced filters by category, source, score range

---

### 8. **Professional UI with cBrain Branding**

**Design Elements:**
- **Colors**: cBrain brand palette (blue, teal, red)
- **Theme**: Dark mode optimized for readability
- **Layout**: Clean, organized information hierarchy
- **Icons**: Visual cues for quick scanning

**Pages:**
- **Scan Results**: Table view with sorting
- **Tender Details**: Complete information page
- **Source Management**: Add/manage/favorite sources
- **Favorites View**: Dedicated page for starred items
- **Saved View**: View all saved tenders

**Navigation:**
```
Main Menu:
- Scan (main dashboard)
- Favorites (starred tenders)
- Saved (bookmarked tenders)
- Sources (tender source management)
```

---

### 9. **Automatic Categorization**

**Categories:**
1. **EDMS / Records Management**: Document management, archiving, registry
2. **Case / Workflow**: Case management, permits, licensing, complaints
3. **ICT / Software**: Software solutions, platforms, applications
4. **Procurement / Consulting**: Consulting services, RFPs, bids
5. **Infrastructure**: Construction, roads, buildings, civil works

**How It Works:**
- System analyzes tender text
- Assigns primary category
- Calculates confidence score
- Displays on detail page

**Benefits:**
- Quick understanding of tender type
- Filter by category (future feature)
- Organize opportunities by business unit

---

### 10. **Data Organization & Storage**

**What's Stored:**
- Tender title, description, link
- Buyer organization
- Country/region
- Deadline date
- Relevance score
- Matched keywords
- Scoring breakdown (JSON)
- Category & confidence
- Save/favorite status
- Discovery date

**Database:**
- SQLite (local, file-based)
- Stores up to 100,000+ records
- Automatic backups recommended
- Exportable data

**Access:**
- View all stored tenders
- Export to CSV (future feature)
- Delete individual records
- Delete all results at once

---

## 📊 Workflow Example

### Scenario: Finding EDMS Tenders for Kenya

**Step 1: Run a Scan**
```
User: Clicks "Run Scan"
System: Searches 8 tender sources
Result: Discovers 45 new tenders
Time: ~45 seconds
```

**Step 2: Review Results**
```
Results shown sorted by score:
1. "Digital Records Management System" - 87% ⭐
2. "Government EDMS Implementation" - 84%
3. "Document Digitization Project" - 76%
4. "Records Management Consultant" - 65%
...
```

**Step 3: View Details**
```
User: Clicks on tender #1
System: Shows:
- Full tender information
- Why it scored 87% (matched EDMS keywords)
- Which keywords were matched
- Link to original source
```

**Step 4: Take Action**
```
User Options:
- Click link to apply directly
- Mark as favorite (⭐)
- Save for later (bookmark)
- Review other similar tenders
```

**Step 5: Track Progress**
```
User: Goes to "Favorites" menu
View: All starred tenders (best matches)
```

---

## 🎯 Use Cases

### 1. **Opportunity Hunting**
- Run daily scans to find new opportunities
- Star the best matches
- Apply to most relevant ones

### 2. **Portfolio Building**
- Save interesting opportunities
- Review later when you have capacity
- Track which sectors have most opportunities

### 3. **Competitive Analysis**
- View which organizations are procuring
- Identify market trends
- Notice repeated tender types

### 4. **Targeted Sourcing**
- Add specific organization tenders as source
- Monitor for opportunities from key clients
- Get immediate notifications

### 5. **Business Development**
- Identify new sectors to enter
- Find consulting/partnership opportunities
- Track competitors' bids

---

## 🔄 Regular Workflow

### Daily Routine
```
1. Open TenderWatch (morning)
2. Click "Run Scan" (2 minutes wait)
3. Review top-scored new tenders
4. Star most interesting ones
5. Visit sources for top 2-3 matches
6. Plan follow-up actions
```

### Weekly Review
```
1. Check "Favorites" page
2. Review saved but not yet reviewed tenders
3. Delete less relevant saved items
4. Update source list if needed
5. Plan next week's pursuit strategy
```

### Monthly Analysis
```
1. Export all discovered tenders
2. Analyze trends and patterns
3. Identify most productive sources
4. Plan source optimization
5. Review winning bids
```

---

## 💡 Pro Tips

### Maximize Results
- ✅ Add region-specific tender sources
- ✅ Customize keywords for your domain
- ✅ Run scans regularly (daily recommended)
- ✅ Review scoring breakdown to understand matches

### Better Scoring
- ✅ System learns from your actions
- ✅ Mark favorites frequently
- ✅ Save tenders you pursue
- ✅ Delete irrelevant results regularly

### Effective Management
- ✅ Use favorites for hot opportunities
- ✅ Save for deeper review later
- ✅ Sort by deadline when urgent
- ✅ Check specific sources when researching

---

## 🎓 Learning Curve

### First 5 Minutes
- Understand main dashboard
- Run first scan
- View results

### First 30 Minutes
- Explore tender details
- Add custom source
- Use favorites and save features

### First Day
- Master all features
- Optimize source list
- Develop scanning routine

### First Week
- Establish daily scanning habit
- Customize keywords if desired
- Start pursuing opportunities

---

## 📱 Accessibility

**Device Support:**
- ✅ Desktop (primary)
- ✅ Tablet (responsive)
- ✅ Mobile (basic support)

**Browser Support:**
- Chrome/Edge (recommended)
- Firefox
- Safari

**Speed:**
- Scan: 30-60 seconds
- Page loads: <1 second
- Search: <100ms

---

## 🔐 Data Safety

**Database:**
- Stored locally on your computer/server
- No cloud sync by default
- Regular backups recommended

**Privacy:**
- No data sent to external services
- Only your tender sources are used
- Complete local control

---

## 📞 Getting Help

### For Setup Issues
See: **QUICKSTART.md**

### For Deployment
See: **DEPLOYMENT.md**

### For Complete Docs
See: **README.md**

### For Feature Details
See: **This document** or tender detail pages

---

## ✨ Summary

TenderWatch provides a complete solution for discovering, analyzing, and managing tender opportunities. With intelligent scoring, detailed breakdowns, and professional UI, it's designed to help cBrain find the best-fit opportunities quickly and efficiently.

**Key differentiators:**
- 🎯 Domain-specific relevance scoring
- 📊 Transparent scoring explanations
- ⭐ Favorites and save functionality
- 🔗 Direct source access
- 🌍 Kenya and global coverage
- 🎨 Professional cBrain branding

**Start using today:** `python run.py`

---

**TenderWatch Features Overview** - Complete Guide
