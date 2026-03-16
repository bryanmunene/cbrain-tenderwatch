"""
Re-score all existing tenders with the latest scoring logic.
Run this after updating scoring.py to refresh all tender scores.
"""
from app import create_app
from app.models import AppSettings, TenderResult
from app.extensions import db
from app.scoring import score_tender
from app.categorizer import categorize
import json

def rescore_all_tenders():
    app = create_app(start_scheduler=False)
    
    with app.app_context():
        settings = AppSettings.query.first()
        tenders = TenderResult.query.all()
        total = len(tenders)
        updated = 0
        excluded = 0
        
        print(f"Re-scoring {total} tenders...")
        print("=" * 60)
        
        for i, t in enumerate(tenders):
            old_score = t.score
            
            # Re-score with latest logic
            source = t.source
            source_group = getattr(source, "source_group", "") or getattr(t, "source_group", "") or "experimental"
            source_tags = getattr(source, "source_tags", "") or json.dumps([source_group])
            new_score, matched, breakdown_json, ranking_score = score_tender(
                t.title,
                t.description_translated or t.description or t.title,
                buyer=t.buyer or (source.name if source else ""),
                country=t.country or "",
                source_name=(source.name if source else (t.search_source or "")),
                source_url=(source.url if source else (t.link or "")),
                source_group=source_group,
                source_tags=source_tags,
                pipeline_mode=getattr(t, "scan_pipeline", "") or "africa_priority",
                settings=settings,
            )
            breakdown = json.loads(breakdown_json)
            
            # Check if excluded
            if breakdown.get("excluded", False):
                print(f"EXCLUDED: {t.title[:50]}... ({breakdown.get('exclusion_reason', '')})")
                db.session.delete(t)
                excluded += 1
                continue
            
            # Update tender with new scoring
            t.score = new_score
            t.ranking_score = ranking_score
            t.keywords_matched = matched
            t.scoring_breakdown = breakdown_json
            
            # Update F2 classification fields
            t.inferred_domains = json.dumps(breakdown.get("domains_matched", []))
            t.priority_level = breakdown.get("priority", "LOW")
            t.likely_fit_for_f2 = breakdown.get("likely_fit_for_F2", "uncertain")
            t.procurement_status = breakdown.get("procurement_status", "open")
            t.requires_qualification = breakdown.get("requires_qualification", False)
            t.qualification_reason = breakdown.get("qualification_reason", "")
            t.source_group = breakdown.get("source_group", source_group)
            t.geographic_scope = breakdown.get("geographic_scope", "Unknown")
            t.region = breakdown.get("region", "")
            t.africa_priority_flag = bool(breakdown.get("africa_priority_flag", False))
            t.donor_or_multilateral_flag = bool(breakdown.get("donor_or_multilateral_flag", False))
            t.target_beneficiary_region = breakdown.get("target_beneficiary_region", "")
            t.buyer_region = breakdown.get("buyer_region", "")
            t.implementation_region = breakdown.get("implementation_region", "")
            t.recommendation = breakdown.get("recommendation", "REVIEW")
            t.queue_bucket = breakdown.get("queue_bucket", "main_shortlist")
            
            # Re-categorize
            category, _, confidence = categorize(t.title, t.title)
            t.category = category
            t.confidence = confidence
            
            if abs(new_score - old_score) > 1:
                print(f"[{i+1}/{total}] {old_score:.1f} -> {new_score:.1f} | {t.title[:40]}...")
                updated += 1
        
        db.session.commit()
        
        print()
        print("=" * 60)
        print(f"COMPLETE: {updated} updated, {excluded} excluded, {total - updated - excluded} unchanged")
        
        # Show new distribution
        high = TenderResult.query.filter(TenderResult.score >= 30).count()
        medium = TenderResult.query.filter(TenderResult.score >= 15, TenderResult.score < 30).count()
        low = TenderResult.query.filter(TenderResult.score < 15).count()
        
        print()
        print("NEW SCORE DISTRIBUTION:")
        print(f"  High (30+): {high}")
        print(f"  Medium (15-29): {medium}")
        print(f"  Low (<15): {low}")


if __name__ == "__main__":
    rescore_all_tenders()

