"""Analyze current tenders for improvement opportunities"""
from app import create_app
from app.models import TenderResult, TenderSource
from app.scoring import score_text
import json

app = create_app(start_scheduler=False)
with app.app_context():
    # Stats
    total = TenderResult.query.count()
    sources = TenderSource.query.count()
    saved = TenderResult.query.filter_by(saved=True).count()
    favorited = TenderResult.query.filter_by(favorite=True).count()
    
    print(f"CURRENT STATE:")
    print(f"  Total tenders: {total}")
    print(f"  Sources: {sources}")
    print(f"  Saved: {saved}")
    print(f"  Favorited: {favorited}")
    print()
    
    # Re-score sample tenders
    print("SAMPLE TENDER RE-SCORING:")
    print("="*70)
    for t in TenderResult.query.limit(5).all():
        score, matched, bd_json = score_text(t.title, t.title)
        bd = json.loads(bd_json)
        print(f"Title: {t.title[:60]}")
        print(f"  DB Score: {t.score} | Recalc: {score}")
        print(f"  Matched: {bd.get('matched_keywords', [])[:5]}")
        print(f"  Domains: {bd.get('domains_matched', [])}")
        if bd.get('excluded'):
            print(f"  EXCLUDED: {bd.get('exclusion_reason')}")
        print()
    
    # Score distribution
    high = TenderResult.query.filter(TenderResult.score >= 30).count()
    medium = TenderResult.query.filter(TenderResult.score >= 15, TenderResult.score < 30).count()
    low = TenderResult.query.filter(TenderResult.score < 15).count()
    
    print(f"SCORE DISTRIBUTION:")
    print(f"  High (30+): {high}")
    print(f"  Medium (15-29): {medium}")
    print(f"  Low (<15): {low}")
    print()
    
    # Domain coverage
    print(f"DOMAIN ANALYSIS:")
    domain_counts = {}
    for t in TenderResult.query.all():
        try:
            domains = json.loads(t.inferred_domains) if t.inferred_domains else []
            for d in domains:
                domain_counts[d] = domain_counts.get(d, 0) + 1
        except:
            pass
    
    for domain, count in sorted(domain_counts.items(), key=lambda x: -x[1]):
        print(f"  {domain}: {count}")
    print()
    
    # Procurement status
    print(f"PROCUREMENT STATUS:")
    statuses = {}
    for t in TenderResult.query.all():
        status = t.procurement_status or "unknown"
        statuses[status] = statuses.get(status, 0) + 1
    
    for status, count in sorted(statuses.items(), key=lambda x: -x[1]):
        print(f"  {status}: {count}")

