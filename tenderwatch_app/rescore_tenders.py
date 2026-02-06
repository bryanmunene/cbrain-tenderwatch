"""
Re-score all existing tenders with the latest scoring logic.
Run this after updating scoring.py to refresh all tender scores.
"""
from app import create_app
from app.models import TenderResult
from app.extensions import db
from app.scoring import score_text
from app.categorizer import categorize
import json

def rescore_all_tenders():
    app = create_app()
    
    with app.app_context():
        tenders = TenderResult.query.all()
        total = len(tenders)
        updated = 0
        excluded = 0
        
        print(f"Re-scoring {total} tenders...")
        print("=" * 60)
        
        for i, t in enumerate(tenders):
            old_score = t.score
            
            # Re-score with latest logic
            new_score, matched, breakdown_json = score_text(t.title, t.description_translated or t.title)
            breakdown = json.loads(breakdown_json)
            
            # Check if excluded
            if breakdown.get("excluded", False):
                print(f"EXCLUDED: {t.title[:50]}... ({breakdown.get('exclusion_reason', '')})")
                db.session.delete(t)
                excluded += 1
                continue
            
            # Update tender with new scoring
            t.score = new_score
            t.keywords_matched = matched
            t.scoring_breakdown = breakdown_json
            
            # Update F2 classification fields
            t.inferred_domains = json.dumps(breakdown.get("domains_matched", []))
            t.priority_level = breakdown.get("priority", "LOW")
            t.likely_fit_for_f2 = breakdown.get("likely_fit_for_F2", "uncertain")
            t.procurement_status = breakdown.get("procurement_status", "open")
            t.requires_qualification = breakdown.get("requires_qualification", False)
            t.qualification_reason = breakdown.get("qualification_reason", "")
            
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
