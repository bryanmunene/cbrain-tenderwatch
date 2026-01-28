import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime, timedelta

from app.deadlines import parse_deadline
from app.source_bias import SOURCE_BIAS
from app.categorizer import categorize
from app.learner import learn_keywords
from app.translator import translate_to_english

from app.extensions import db
from app.models import TenderSource, TenderResult
from app.scoring import score_text

# Country mapping for tender sources
COUNTRY_MAP = {
    # Kenya sources
    "kenya": "Kenya",
    "undp kenya": "Kenya",
    "world bank": "Kenya",
    "usaid": "Kenya",
    "afdb": "Kenya",
    # Global sources
    "undb": "Global",
    "gef": "Global",
    "ifc": "Global",
    "unops": "Global",
    # Default
    "undp": "Global",
}


def scan_source(source: TenderSource):
    new_tenders = []
    try:
        # Try with SSL verification first, fallback to no verification if it fails
        try:
            html = requests.get(source.url, timeout=30, verify=True).text
        except requests.exceptions.SSLError:
            print(f"⚠️  SSL Error for {source.name}, retrying without verification...")
            html = requests.get(source.url, timeout=30, verify=False).text
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to fetch {source.name}: {str(e)}")
        return new_tenders
    
    soup = BeautifulSoup(html, "html.parser")

    existing = {r.link for r in TenderResult.query.all()}

    # Find all links - focus on specific tender/procurement pages
    links_to_process = []
    
    for a in soup.find_all("a", href=True):
        href = a["href"]
        
        # Skip certain types of links
        if any(skip in href.lower() for skip in ["javascript:", "mailto:", "#", "back", "home", "login"]):
            continue
        
        # UNDP-specific links
        if "view_notice.cfm" in href:
            links_to_process.append((a, href, True))
        # Look for procurement/tender pages (but will still need keyword validation)
        elif any(pattern in href.lower() for pattern in ["tender", "procurement", "opportunity"]):
            links_to_process.append((a, href, True))
        # Generic links with substantive text (likely tender titles)
        elif len(a.get_text(strip=True)) > 30:  # Increased from 20 to 30 for more specificity
            links_to_process.append((a, href, False))
    
    for a, href, is_likely_tender in links_to_process:
        full_url = urljoin(source.url, href)
        if full_url in existing:
            continue

        title = a.get_text(strip=True) or "Tender Opportunity"
        
        # Clean up title - remove common prefixes
        for prefix in ["Title", "Tender", "Notice", "Opportunity"]:
            if title.lower().startswith(prefix.lower()):
                title = title[len(prefix):].strip()
        
        # Skip very short titles
        if len(title) < 10:
            continue
        
        score, matched, scoring_breakdown = score_text(title, title)

        if score == 0:
            continue  # Skip if no keywords match

        # Apply deterministic per-source bias
        bias = SOURCE_BIAS.get(source.name.lower(), 0)
        score = min(100, score + bias)

        # Categorize + learn
        category, _, confidence = categorize(title, title)
        learn_keywords(title, category)

        # Parse deadline from raw text
        raw_text = a.get_text(" ", strip=True)
        deadline = parse_deadline(raw_text)

        # Extract country from source name
        country = "Unknown"
        source_lower = source.name.lower()
        for key, value in COUNTRY_MAP.items():
            if key in source_lower:
                country = value
                break

        # Translate title to English
        title_translated = translate_to_english(title)
        description_translated = ""

        r = TenderResult(
            title=title,
            title_translated=title_translated,
            link=full_url,
            description_translated=description_translated,
            buyer=source.name,
            country=country,
            deadline=deadline,
            score=score,
            keywords_matched=matched,
            scoring_breakdown=scoring_breakdown,
            category=category,
            confidence=confidence,
            source_id=source.id,
            notified=False,
        )

        db.session.add(r)
        new_tenders.append(r)

    db.session.commit()
    print(f"✅ Scanned {source.name}: Found {len(links_to_process)} potential tenders")
    return new_tenders



def cleanup_old_tenders():
    """Remove tenders older than 1 month"""
    one_month_ago = datetime.utcnow() - timedelta(days=30)
    old_tenders = TenderResult.query.filter(TenderResult.created_at < one_month_ago).all()
    
    if old_tenders:
        count = len(old_tenders)
        for tender in old_tenders:
            db.session.delete(tender)
        db.session.commit()
        print(f"🗑️  Removed {count} tender(s) older than 1 month")
    else:
        print("✅ No old tenders to remove")


def run_scan():
    """Scan all active sources for tenders and return newly added tenders"""
    # First, clean up old tenders
    cleanup_old_tenders()
    
    sources = TenderSource.query.filter_by(active=True).all()
    
    if not sources:
        print("⚠️  No active sources found. Add sources and mark them as active to start scanning.")
        return []
    
    print(f"\n🔍 Starting scan of {len(sources)} active source(s)...")
    all_new_tenders = []
    for src in sources:
        print(f"📡 Scanning: {src.name}")
        new_tenders = scan_source(src)
        all_new_tenders.extend(new_tenders)
    
    print("✅ Scan complete!")
    return all_new_tenders
