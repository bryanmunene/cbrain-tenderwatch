from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, Iterable, List, Optional, Tuple

import joblib
import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.pipeline import Pipeline

from app.extensions import db
from app.models import FeedbackEvent, TenderResult

MODEL_DIR = Path("instance")
MODEL_PATH = MODEL_DIR / "relevance_model.joblib"


@dataclass
class TrainResult:
    trained: bool
    message: str
    samples: int = 0
    positives: int = 0
    negatives: int = 0


def _parse_json(raw: str) -> Dict:
    if not raw:
        return {}
    try:
        return json.loads(raw) if isinstance(raw, str) else dict(raw)
    except Exception:
        return {}


def _extract_features(t: TenderResult) -> Dict:
    breakdown = _parse_json(getattr(t, "scoring_breakdown", "") or "")
    matched = (getattr(t, "keywords_matched", "") or "").lower()
    keyword_count = len([x for x in matched.split(",") if x.strip()])
    title = (getattr(t, "title_translated", "") or getattr(t, "title", "") or "").lower()
    desc = (getattr(t, "description_translated", "") or getattr(t, "description", "") or "").lower()
    text = f"{title} {desc}"

    has_deadline = 1.0 if (getattr(t, "deadline", "") or "").strip() else 0.0
    has_direct_doc_phrase = 1.0 if any(
        p in text
        for p in [
            "document management system",
            "records management system",
            "workflow management system",
            "electronic document",
            "electronic records",
            "case management system",
            "business process management",
        ]
    ) else 0.0

    domains = breakdown.get("domains_matched", []) or []
    likely_fit = (breakdown.get("likely_fit_for_F2", "") or getattr(t, "likely_fit_for_f2", "") or "").lower()
    procurement_status = (breakdown.get("procurement_status", "") or getattr(t, "procurement_status", "") or "").lower()
    timing_status = (getattr(t, "timing_status", "") or "").lower()
    priority = (getattr(t, "priority_level", "") or "").upper()

    return {
        "score": float(getattr(t, "score", 0.0) or 0.0),
        "keyword_count": float(keyword_count),
        "has_deadline": has_deadline,
        "has_direct_doc_phrase": has_direct_doc_phrase,
        "source_id": f"src_{getattr(t, 'source_id', 0) or 0}",
        "country": f"cty_{(getattr(t, 'country', '') or 'unknown').lower()}",
        "category": f"cat_{(getattr(t, 'category', '') or 'unknown').lower()}",
        "priority": f"prio_{priority or 'LOW'}",
        "fit": f"fit_{likely_fit or 'uncertain'}",
        "procurement_status": f"ps_{procurement_status or 'open'}",
        "timing": f"tm_{timing_status or 'open'}",
        "domains": "|".join(sorted([str(d).lower() for d in domains])) if domains else "",
    }


def _build_dataset(days: int = 180, max_samples: int = 5000) -> Tuple[List[Dict], List[int]]:
    since = datetime.utcnow() - timedelta(days=days)
    feedback = (
        FeedbackEvent.query
        .filter(FeedbackEvent.created_at >= since)
        .order_by(FeedbackEvent.created_at.desc())
        .limit(max_samples)
        .all()
    )

    X: List[Dict] = []
    y: List[int] = []

    for fb in feedback:
        tender = TenderResult.query.get(fb.tender_id)
        if not tender:
            continue
        label = 1 if float(fb.label_weight or 0) > 0 else 0
        X.append(_extract_features(tender))
        y.append(label)

    return X, y


def train_relevance_model(min_samples: int = 50) -> TrainResult:
    X, y = _build_dataset()
    if len(X) < min_samples:
        return TrainResult(False, f"Need at least {min_samples} feedback samples.", samples=len(X))

    positives = int(sum(y))
    negatives = int(len(y) - positives)
    if positives == 0 or negatives == 0:
        return TrainResult(False, "Need both positive and negative feedback labels.", samples=len(X), positives=positives, negatives=negatives)

    pipeline = Pipeline(
        [
            ("vec", DictVectorizer(sparse=True)),
            ("clf", SGDClassifier(loss="log_loss", alpha=1e-4, max_iter=1500, tol=1e-3, class_weight="balanced", random_state=42)),
        ]
    )
    pipeline.fit(X, y)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "pipeline": pipeline,
            "trained_at": datetime.utcnow().isoformat(),
            "samples": len(X),
            "positives": positives,
            "negatives": negatives,
        },
        MODEL_PATH,
    )
    return TrainResult(True, "Model trained successfully.", samples=len(X), positives=positives, negatives=negatives)


def _load_model():
    if not MODEL_PATH.exists():
        return None
    try:
        return joblib.load(MODEL_PATH)
    except Exception:
        return None


def model_status() -> Dict:
    mdl = _load_model()
    if not mdl:
        return {"available": False, "trained_at": None, "samples": 0, "positives": 0, "negatives": 0}
    return {
        "available": True,
        "trained_at": mdl.get("trained_at"),
        "samples": int(mdl.get("samples", 0) or 0),
        "positives": int(mdl.get("positives", 0) or 0),
        "negatives": int(mdl.get("negatives", 0) or 0),
    }


def feedback_counts(days: int = 180) -> Dict:
    since = datetime.utcnow() - timedelta(days=days)
    q = FeedbackEvent.query.filter(FeedbackEvent.created_at >= since)
    total = q.count()
    pos = q.filter(FeedbackEvent.label_weight > 0).count()
    neg = q.filter(FeedbackEvent.label_weight <= 0).count()
    return {"total": total, "positive": pos, "negative": neg}


def predict_relevance(tender: TenderResult) -> Optional[float]:
    mdl = _load_model()
    if not mdl:
        return None
    try:
        pipeline = mdl["pipeline"]
        proba = pipeline.predict_proba([_extract_features(tender)])[0][1]
        return float(np.clip(proba, 0.0, 1.0))
    except Exception:
        return None


def blend_score(rule_score: float, ml_score: Optional[float], alpha: float = 0.72) -> float:
    if ml_score is None:
        return float(rule_score)
    ml_percent = ml_score * 100.0
    return float((alpha * float(rule_score)) + ((1.0 - alpha) * ml_percent))


def record_feedback(tender_id: int, event_type: str, label_weight: float) -> bool:
    try:
        fb = FeedbackEvent(
            tender_id=int(tender_id),
            event_type=str(event_type or "unknown")[:50],
            label_weight=float(label_weight),
        )
        db.session.add(fb)
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        return False


def _compat_subject(
    title: str,
    description: str,
    rule_score: float,
    keywords_matched: str,
    scoring_breakdown: str,
):
    """Build a text-only tender-like object for legacy compatibility APIs."""
    return SimpleNamespace(
        title=title or "",
        title_translated=title or "",
        description=description or "",
        description_translated=description or "",
        score=float(rule_score or 0.0),
        keywords_matched=keywords_matched or "",
        scoring_breakdown=scoring_breakdown or "",
        deadline="",
        source_id=0,
        country="unknown",
        category="unknown",
        priority_level="LOW",
        likely_fit_for_f2="uncertain",
        procurement_status="open",
        timing_status="open",
    )


# ---------------------------------------------------------------------------
# Legacy compatibility layer.
# Older Flask routes/tests import these names, so keep them available.
# ---------------------------------------------------------------------------
def extract_features(title: str, description: str = "") -> Dict:
    from app.scoring import score_text

    t = str(title or "")
    d = str(description or "")
    rule_score, matched, breakdown = score_text(t, d)
    subject = _compat_subject(t, d, rule_score, matched, breakdown)
    return _extract_features(subject)


def get_model_status() -> Dict:
    mdl = model_status()
    try:
        fb = feedback_counts(days=3650)
    except Exception:
        # Support CLI/test callers that query status outside Flask app context.
        fb = {"total": 0, "positive": 0, "negative": 0}
    available = bool(mdl.get("available"))
    return {
        # New fields
        "available": available,
        "trained_at": mdl.get("trained_at"),
        "samples": int(mdl.get("samples", 0) or 0),
        "positives": int(mdl.get("positives", 0) or 0),
        "negatives": int(mdl.get("negatives", 0) or 0),
        # Legacy fields expected by old UI/routes
        "sentence_model_loaded": available,
        "ranker_model_loaded": available,
        "golden_tenders_count": int(fb.get("positive", 0) or 0),
        "ranker_trained_at": mdl.get("trained_at"),
        "ranker_positive_count": int(mdl.get("positives", 0) or 0),
        "ranker_negative_count": int(mdl.get("negatives", 0) or 0),
        "feedback_total": int(fb.get("total", 0) or 0),
    }


def update_golden_embeddings() -> bool:
    """
    Compatibility shim for previous semantic-embedding pipeline.
    We now store positive preference signals in feedback events.
    """
    try:
        preferred_ids = [
            int(row[0])
            for row in (
                db.session.query(TenderResult.id)
                .filter((TenderResult.saved.is_(True)) | (TenderResult.favorite.is_(True)))
                .all()
            )
        ]
        if not preferred_ids:
            return False

        existing = {
            int(row[0])
            for row in (
                db.session.query(FeedbackEvent.tender_id)
                .filter(
                    FeedbackEvent.event_type == "golden_sync",
                    FeedbackEvent.tender_id.in_(preferred_ids),
                )
                .all()
            )
        }

        new_events = 0
        for tid in preferred_ids:
            if tid in existing:
                continue
            db.session.add(
                FeedbackEvent(
                    tender_id=tid,
                    event_type="golden_sync",
                    label_weight=1.0,
                )
            )
            new_events += 1

        if new_events:
            db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        return False


def train_ranker_model(min_samples: int = 40) -> Tuple[bool, str]:
    result = train_relevance_model(min_samples=min_samples)
    return result.trained, result.message


def ml_score(title: str, description: str = "") -> Dict:
    from app.scoring import score_text

    t = str(title or "")
    d = str(description or "")
    keyword_score, matched, breakdown_raw = score_text(t, d)

    try:
        breakdown = json.loads(breakdown_raw) if breakdown_raw else {}
    except Exception:
        breakdown = {}

    subject = _compat_subject(t, d, keyword_score, matched, breakdown_raw)
    ml_prob = predict_relevance(subject)
    final = blend_score(keyword_score, ml_prob)
    method = "keyword+relevance-model" if ml_prob is not None else "keyword-only"
    semantic_pct = float((ml_prob or 0.0) * 100.0)

    flags = []
    if breakdown.get("platform_commitment_signals"):
        flags.append("platform commitment")
    if breakdown.get("irrelevant_signals"):
        flags.append("irrelevant signal")

    explanation_parts = [f"Rule score {float(keyword_score):.1f}."]
    if ml_prob is None:
        explanation_parts.append("No trained relevance model available.")
    else:
        explanation_parts.append(f"Model confidence {semantic_pct:.1f}%.")
    if flags:
        explanation_parts.append(f"Detected: {', '.join(flags)}.")

    return {
        "method": method,
        "keyword_score": float(keyword_score),
        "semantic_score": semantic_pct,
        "final_score": float(final),
        "explanation": " ".join(explanation_parts),
        "matched_keywords": matched,
        "breakdown": breakdown,
    }
