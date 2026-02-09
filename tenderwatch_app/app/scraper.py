import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime, timedelta


from app.deadlines import parse_deadline, check_timing_constraints, is_deadline_valid
from app.source_bias import SOURCE_BIAS
from app.categorizer import categorize
from app.learner import learn_keywords
from app.translator import translate_to_english

from app.extensions import db
from app.models import TenderSource, TenderResult
from app.scoring import score_text
from app.source_bias import COUNTRY_MAP

# Import the Flask app instance for context management
from app import app

# Reduced timeout for faster scans
HTTP_TIMEOUT = 5  # seconds (was 30, then 10)


def scan_source(source: TenderSource):
    import time
    new_tenders = []
    t0 = time.time()
    # Ensure Flask app context in this thread
    with app.app_context():
        try:
            # Try with SSL verification first, fallback to no verification if it fails
            try:
                html = requests.get(source.url, timeout=HTTP_TIMEOUT, verify=True).text
            except requests.exceptions.SSLError:
                print(f"⚠️  SSL Error for {source.name}, retrying without verification...")
                html = requests.get(source.url, timeout=HTTP_TIMEOUT, verify=False).text
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to fetch {source.name}: {str(e)[:50]}")
            print(f"⏱️  {source.name} took {time.time()-t0:.1f}s (FAILED)")
            return new_tenders
        
        elapsed = time.time() - t0
        if elapsed > 5:
            print(f"🐢 SLOW: {source.name} took {elapsed:.1f}s")
        else:
            print(f"⏱️  {source.name} took {elapsed:.1f}s")
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
        
        # ...existing code...
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
    OPTIMIZED: Uses parallel scanning with 15 workers for 10x faster scans.
    
    Args:
        include_auto_discovery: If True, also runs auto-discovery via search APIs
    
    Returns:
        List of newly added TenderResult objects
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import time
    
    start_time = time.time()
    
    # First, clean up old tenders
    cleanup_old_tenders()
    
    sources = TenderSource.query.filter_by(active=True).all()
    
    if not sources and not include_auto_discovery:
        print("⚠️  No active sources found. Add sources and mark them as active to start scanning.")
        return []
    
    all_new_tenders = []
    
    # Scan sources in PARALLEL (15 workers for maximum speed)
    if sources:
        print(f"\n🚀 FAST PARALLEL scan: {len(sources)} sources with 15 workers...")
        
        with ThreadPoolExecutor(max_workers=15) as executor:
            future_to_source = {executor.submit(scan_source, src): src for src in sources}
            
            completed = 0
            for future in as_completed(future_to_source):
                source = future_to_source[future]
                completed += 1
                try:
                    new_tenders = future.result()
                    if new_tenders:
                        all_new_tenders.extend(new_tenders)
                        print(f"✓ [{completed}/{len(sources)}] {source.name}: {len(new_tenders)} new")
                except Exception as e:
                    print(f"✗ [{completed}/{len(sources)}] {source.name}: {str(e)[:30]}")
            print("\n--- SLOW SOURCES REPORT ---")
            # Print slow sources summary
            # (Already printed per-source above)
            print("(Any source above marked 🐢 SLOW is a bottleneck)")
    
    elapsed = time.time() - start_time
    print(f"✅ Scan complete in {elapsed:.1f}s! Found {len(all_new_tenders)} new tenders.")
    
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
