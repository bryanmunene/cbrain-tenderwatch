from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
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
