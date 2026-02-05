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

    # Navigation/menu text patterns to exclude (case-insensitive)
    NAV_PATTERNS = {
        # Generic navigation
        "about us", "about", "contact us", "contact", "home", "login", "sign in", "register",
        "search", "help", "faq", "privacy", "terms", "cookie", "accessibility",
        "menu", "navigation", "sitemap", "site map", "back to top", "read more", "learn more",
        "click here", "view all", "see all", "show more", "load more",
        # Organization info
        "who we are", "what we do", "how we work", "our work", "our team", "our partners",
        "our office", "our history", "our mission", "our vision", "our values",
        "careers", "jobs", "employment", "vacancies", "work with us", "join us",
        # Procurement info pages (not actual tenders)
        "how we buy", "what we buy", "how to apply", "how to register", "how to submit",
        "qualifications", "eligibility", "supplier", "vendor", "guidance", "guidelines",
        "resources", "training", "certification", "statistics", "reports", "annual report",
        "code of conduct", "protest", "sanctions", "policies", "procedures",
        "guiding principles", "strategy", "sustainable", "framework",
        # Social/sharing
        "facebook", "twitter", "linkedin", "instagram", "youtube", "share", "follow us",
        "subscribe", "newsletter", "email us", "call us",
        # Document types (not tenders)
        "press release", "news", "blog", "article", "publication", "brochure",
        "annual report", "quarterly report", "financial report",
    }
    
    # Find all links - focus on specific tender/procurement pages
    links_to_process = []
    
    for a in soup.find_all("a", href=True):
        href = a["href"]
        
        # Skip certain types of links
        if any(skip in href.lower() for skip in ["javascript:", "mailto:", "#", "back", "home", "login"]):
            continue
        
        # Get and clean link text
        link_text = a.get_text(strip=True).lower()
        
        # Skip navigation/menu links
        if any(nav in link_text for nav in NAV_PATTERNS):
            continue
        
        # Skip very short or very long text (likely UI elements or paragraphs)
        if len(link_text) < 15 or len(link_text) > 300:
            continue
        
        # UNDP-specific links (known tender patterns)
        if "view_notice.cfm" in href or "notice_id=" in href:
            links_to_process.append((a, href, True))
        # DevBusiness/UNDB patterns
        elif any(p in href.lower() for p in ["/node/", "/tender/", "/opportunity/", "/notice/"]):
            links_to_process.append((a, href, True))
        # Generic tender/procurement links
        elif any(pattern in href.lower() for pattern in ["tender", "procurement", "rfp", "rfq", "bid"]):
            links_to_process.append((a, href, True))
        # Links with tender-like text patterns
        elif any(kw in link_text for kw in ["tender", "rfp", "rfq", "bid", "procurement", "contract", "consultancy", "supply of", "provision of", "services for"]):
            links_to_process.append((a, href, True))
        # Generic links with substantive text (potential tender titles)
        elif len(a.get_text(strip=True)) > 40:  # Increased threshold for more specificity
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
        if len(title) < 15:
            continue
        
        # Final navigation check on title (double-check)
        title_lower = title.lower()
        if any(nav in title_lower for nav in NAV_PATTERNS):
            continue
        
        # Skip generic info pages that aren't real tenders
        GENERIC_INFO_PATTERNS = {
            "procurement at undp", "office of procurement", "procurement office",
            "how to do business", "doing business with", "become a supplier",
            "vendor registration", "supplier registration", "procurement process",
            "procurement policy", "procurement manual", "procurement guide",
        }
        if any(info in title_lower for info in GENERIC_INFO_PATTERNS):
            continue
        
        # Check if this looks like a real tender (has reference number or specific patterns)
        import re
        has_ref_number = bool(re.search(r'(ref\s*no|undp-|unw-|unops-|rfp-|rfq-|\d{4,}[-/]\d+)', title_lower))
        has_tender_keywords = any(kw in title_lower for kw in [
            "supply of", "provision of", "services for", "consultancy", "consultant",
            "construction", "renovation", "installation", "procurement of", "purchase of",
            "request for proposal", "request for quotation", "invitation to bid",
            "equipment", "vehicle", "furniture", "solar", "drilling", "training",
            "lta for", "ita for", "ic/", "rfp for", "rfq for"
        ])
        
        # For non-likely tenders (generic links), require stronger evidence
        if not is_likely_tender and not has_ref_number and not has_tender_keywords:
            continue
        
        # AI-enhanced scoring
        from app.models import AppSettings
        from sqlalchemy.orm import Session
        # Disable autoflush to prevent IntegrityError on pending objects
        with db.session.no_autoflush:
            settings = AppSettings.query.first()
        use_ai = settings and settings.ai_scoring_enabled if settings else False
        
        if use_ai:
            try:
                from app.ai_scoring import hybrid_score
                score, matched, scoring_breakdown_dict = hybrid_score(title, title)
                scoring_breakdown = str(scoring_breakdown_dict)
                semantic_score = scoring_breakdown_dict.get('semantic_score', score)
                ai_confidence = scoring_breakdown_dict.get('semantic_confidence', 0.5)
            except:
                # Fallback to traditional scoring
                score, matched, scoring_breakdown = score_text(title, title)
                semantic_score = 0
                ai_confidence = 0
        else:
            score, matched, scoring_breakdown = score_text(title, title)
            semantic_score = 0
            ai_confidence = 0

        # ONLY save tenders that match cBrain keywords (document management, case management, workflow, e-gov)
        # Skip tenders that don't match any relevant keywords
        if score == 0:
            continue  # Not relevant to cBrain - skip entirely
        
        # Ensure scoring_breakdown is a string
        if isinstance(scoring_breakdown, dict):
            import json
            scoring_breakdown = json.dumps(scoring_breakdown)

        # Apply deterministic per-source bias
        bias = SOURCE_BIAS.get(source.name.lower(), 0)
        score = min(100, score + bias)

        # Categorize (don't learn keywords yet - do it after commit)
        category, _, confidence = categorize(title, title)
        
        # Parse deadline from raw text first
        raw_text = a.get_text(" ", strip=True)
        deadline = parse_deadline(raw_text)
        
        # Extract country from source name
        country = "Unknown"
        source_lower = source.name.lower()
        for key, value in COUNTRY_MAP.items():
            if key in source_lower:
                country = value
                break
        
        # Extract entities with AI (may override deadline/buyer)
        entities_json = ""
        if use_ai and settings and settings.entity_extraction_enabled:
            try:
                from app.ai_entities import extract_entities
                import json
                entities = extract_entities(title, title)
                entities_json = json.dumps(entities)
                
                # Use extracted deadline if available and original was empty
                if entities.get('deadline') and not deadline:
                    deadline = entities['deadline']
            except Exception as e:
                print(f"⚠️  Entity extraction failed: {e}")

        # Translate title to English and detect original language
        from app.translator import detect_language
        original_lang = detect_language(title)
        
        if original_lang != "en":
            title_translated = translate_to_english(title)
        else:
            title_translated = title  # Already in English
        
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
            semantic_score=semantic_score,
            ai_confidence=ai_confidence,
            entities_extracted=entities_json,
            category=category,
            confidence=confidence,
            source_id=source.id,
            notified=False,
        )

        try:
            db.session.add(r)
            db.session.flush()  # Flush to check for duplicates early
            new_tenders.append(r)
        except Exception as e:
            # Skip duplicate tenders (IntegrityError on unique link constraint)
            db.session.rollback()
            continue

    try:
        db.session.commit()
        # Learn keywords after successful commit
        for tender in new_tenders:
            try:
                learn_keywords(tender.title, tender.category)
            except:
                pass  # Ignore learning errors
    except Exception as e:
        print(f"⚠️  Error committing tenders: {e}")
        db.session.rollback()
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


def run_scan(include_auto_discovery=True):
    """
    Scan sources for tenders and return newly added tenders.
    
    Args:
        include_auto_discovery: If True, also runs auto-discovery via search APIs
    
    Returns:
        List of newly added TenderResult objects
    """
    # First, clean up old tenders
    cleanup_old_tenders()
    
    sources = TenderSource.query.filter_by(active=True).all()
    
    if not sources and not include_auto_discovery:
        print("⚠️  No active sources found. Add sources and mark them as active to start scanning.")
        return []
    
    all_new_tenders = []
    
    # Scan manual/priority sources
    if sources:
        print(f"\n🔍 Starting scan of {len(sources)} active source(s)...")
        for src in sources:
            print(f"📡 Scanning: {src.name}")
            new_tenders = scan_source(src)
            all_new_tenders.extend(new_tenders)
    
    # Auto-discovery is disabled (API setup was too complex)
    # If you have valid API keys, you can re-enable by uncommenting:
    # if include_auto_discovery:
    #     auto_tenders = run_auto_discovery()
    #     all_new_tenders.extend(auto_tenders)
    
    print("✅ Scan complete!")
    
    # Send push notifications for new high-score tenders
    if all_new_tenders:
        try:
            from flask import current_app
            from app.push_notifications import PushNotificationService
            
            push_service = PushNotificationService(current_app._get_current_object())
            push_service.notify_new_tenders(all_new_tenders)
        except Exception as e:
            print(f"⚠️ Push notification failed: {e}")
    
    return all_new_tenders


def run_auto_discovery():
    """
    Run auto-discovery using Google and Bing search APIs.
    
    Returns:
        List of newly added TenderResult objects from auto-discovery
    """
    from app.models import AppSettings, DiscoveryLog
    from app.auto_discovery import get_discovery_engine, get_search_manager, init_discovery
    import json
    import time
    
    start_time = time.time()
    new_tenders = []
    
    # Get settings
    settings = AppSettings.query.first()
    if not settings:
        print("ℹ️  No settings found, auto-discovery skipped")
        return new_tenders
    
    # Check if API keys are configured (run if keys exist, regardless of toggle)
    has_google_keys = settings.google_api_key and settings.google_cx
    has_bing_key = settings.bing_api_key
    
    print(f"🔍 Auto-discovery check:")
    print(f"   Google API Key: {'✓ Present' if settings.google_api_key else '✗ Missing'}")
    print(f"   Google CX: {'✓ Present' if settings.google_cx else '✗ Missing'}")
    print(f"   Bing API Key: {'✓ Present' if settings.bing_api_key else '✗ Missing'}")
    
    if not has_google_keys and not has_bing_key:
        print("⚠️  Auto-discovery: No API keys configured - skipping discovery")
        return new_tenders
    
    print("🌐 Starting auto-discovery with configured APIs...")
    
    # Initialize discovery engine
    try:
        init_discovery(
            google_api_key=settings.google_api_key or None,
            google_cx=settings.google_cx or None,
            bing_api_key=settings.bing_api_key or None
        )
        
        engine = get_discovery_engine()
        manager = get_search_manager()
        
        if not engine or not manager:
            print("⚠️  Auto-discovery engine not initialized (check API keys)")
            return new_tenders
        
    except Exception as e:
        print(f"❌ Failed to initialize auto-discovery: {e}")
        return new_tenders
    
    print(f"\n🌐 Starting auto-discovery (Google + Bing APIs)...")
    
    # Get custom queries or use defaults
    custom_queries = None
    if settings.discovery_queries:
        try:
            custom_queries = json.loads(settings.discovery_queries)
        except:
            pass
    
    # Run discovery
    try:
        discovered = engine.discover_tenders(
            queries=custom_queries,
            results_per_query=settings.results_per_query or 10
        )
        
        print(f"🔍 Auto-discovery found {len(discovered)} potential tenders")
        
        # Process discovered tenders
        existing = {r.link for r in TenderResult.query.all()}
        
        for item in discovered:
            if item['link'] in existing:
                continue
            
            # Score and categorize
            title = item['title']
            description = item.get('description', '')
            
            # Get AI settings
            use_ai = settings and settings.ai_scoring_enabled
            
            # Score with AI or traditional
            if use_ai:
                try:
                    from app.ai_scoring import hybrid_score
                    import json as json_lib
                    score, matched, scoring_breakdown = hybrid_score(title, description)
                    scoring_breakdown_dict = json_lib.loads(scoring_breakdown)
                    semantic_score = scoring_breakdown_dict.get('semantic_score', score)
                    ai_confidence = scoring_breakdown_dict.get('semantic_confidence', 0.5)
                except:
                    score, matched, scoring_breakdown = score_text(title, description)
                    semantic_score = 0
                    ai_confidence = 0
            else:
                score, matched, scoring_breakdown = score_text(title, description)
                semantic_score = 0
                ai_confidence = 0
            
            if score < 10:  # Skip very low scores
                continue
            
            # Categorize
            category, _, confidence = categorize(title, description)
            
            # Translate
            title_translated = translate_to_english(title)
            description_translated = translate_to_english(description)
            
            # Extract entities if AI enabled
            entities_json = ""
            deadline = ""
            buyer = ""
            if use_ai and settings.entity_extraction_enabled:
                try:
                    from app.ai_entities import extract_entities
                    import json as json_lib
                    entities = extract_entities(title, description)
                    entities_json = json_lib.dumps(entities)
                    deadline = entities.get('deadline', '')
                    buyer = entities.get('buyer', '')
                except:
                    pass
            
            # Create tender result
            tender = TenderResult(
                title=title,
                title_translated=title_translated,
                link=item['link'],
                description=description,
                description_translated=description_translated,
                score=score,
                keywords_matched=matched,
                scoring_breakdown=scoring_breakdown,
                discovery_method='auto',
                search_query=item.get('search_query', ''),
                search_source=item.get('search_source', ''),
                semantic_score=semantic_score,
                ai_confidence=ai_confidence,
                entities_extracted=entities_json,
                category=category,
                confidence=confidence,
                deadline=deadline,
                buyer=buyer,
                country="Global",  # Auto-discovered tenders are global by default
                source_id=None  # No source for auto-discovered
            )
            
            db.session.add(tender)
            new_tenders.append(tender)
        
        # Commit all new tenders
        db.session.commit()
        
        # Log discovery run (skip if database is read-only on Streamlit Cloud)
        try:
            quota_status = manager.get_quota_status()
            log = DiscoveryLog(
                run_type='manual',
                queries_run=len(custom_queries) if custom_queries else len(engine.DEFAULT_QUERIES),
                results_found=len(discovered),
                results_saved=len(new_tenders),
                google_quota_used=quota_status['google']['used'],
                bing_quota_used=quota_status['bing']['used'],
                execution_time_seconds=time.time() - start_time
            )
            db.session.add(log)
            db.session.commit()
        except Exception as log_error:
            logger.debug(f"Could not save discovery log (read-only database): {log_error}")
            db.session.rollback()
        
        print(f"✅ Auto-discovery complete: {len(new_tenders)} new tenders added")
        quota_status = manager.get_quota_status()
        print(f"📊 Quota used - Google: {quota_status['google']['used']}/{quota_status['google']['limit']}, Bing: {quota_status['bing']['used']}/{quota_status['bing']['limit']}")
        
    except Exception as e:
        print(f"❌ Auto-discovery failed: {e}")
        db.session.rollback()
        
        # Log error (skip if database is read-only on Streamlit Cloud)
        try:
            log = DiscoveryLog(
                run_type='manual',
                queries_run=0,
                results_found=0,
                results_saved=0,
                execution_time_seconds=time.time() - start_time,
                error_message=str(e)
            )
            db.session.add(log)
            db.session.commit()
        except Exception as log_error:
            logger.debug(f"Could not save discovery error log (read-only database): {log_error}")
            db.session.rollback()
    
    return new_tenders
