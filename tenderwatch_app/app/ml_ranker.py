"""
ML-powered Tender Ranker using LightGBM + Sentence Embeddings
=============================================================

This module implements a hybrid ML approach:
1. Feature Engineering from keyword scoring (explainable)
2. Sentence Embeddings for semantic similarity (understanding)
3. LightGBM Ranker learns optimal weights from user feedback

Training data comes from:
- Saved tenders (label=1)
- Favorited tenders (label=2, weighted higher)
- Non-saved old tenders (label=0, implicit negative)
"""

import os
import json
import logging
import pickle
import numpy as np
from datetime import datetime, timedelta
from functools import lru_cache

logger = logging.getLogger(__name__)

# Model paths
MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')
RANKER_MODEL_PATH = os.path.join(MODEL_DIR, 'lgbm_ranker.pkl')
GOLDEN_EMBEDDINGS_PATH = os.path.join(MODEL_DIR, 'golden_embeddings.pkl')

# Global instances (lazy loaded)
_sentence_model = None
_ranker_model = None
_golden_embeddings = None
_golden_titles = None


def _ensure_model_dir():
    """Create models directory if it doesn't exist"""
    os.makedirs(MODEL_DIR, exist_ok=True)


def get_sentence_model():
    """Load sentence transformer model (lazy, cached)"""
    global _sentence_model
    if _sentence_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("âœ… Sentence transformer loaded")
        except ImportError:
            logger.warning("âš ï¸ sentence-transformers not installed")
            _sentence_model = False
        except Exception as e:
            logger.error(f"âŒ Failed to load sentence model: {e}")
            _sentence_model = False
    return _sentence_model if _sentence_model is not False else None


def extract_features(title: str, text: str = "", scoring_breakdown: dict = None) -> dict:
    """
    Extract ML features from tender text and scoring breakdown.
    
    These features are:
    - Interpretable (can explain to user)
    - Derived from existing keyword system
    - Quick to compute
    
    Returns dict of feature_name: value
    """
    from app.scoring import score_text
    import json
    
    # Get scoring breakdown if not provided
    if scoring_breakdown is None:
        _, _, breakdown_json = score_text(title, text)
        scoring_breakdown = json.loads(breakdown_json)
    
    # Domain presence features (binary)
    domains = set(scoring_breakdown.get('domains_matched', []))
    
    features = {
        # Domain presence (most important for F2)
        'domain_edms': 1 if 'EDMS' in domains else 0,
        'domain_records': 1 if 'Records' in domains else 0,
        'domain_case': 1 if 'Case' in domains else 0,
        'domain_workflow': 1 if 'Workflow' in domains else 0,
        'domain_gov': 1 if 'Gov' in domains else 0,
        'domain_ecm': 1 if 'ECM' in domains else 0,
        'domain_forms': 1 if 'Forms' in domains else 0,
        'domain_service_delivery': 1 if 'ServiceDelivery' in domains else 0,
        
        # Aggregate counts
        'domain_count': len(domains),
        'keyword_count': scoring_breakdown.get('keywords_found', 0),
        
        # Score components
        'base_score': scoring_breakdown.get('base_score', 0),
        'domain_bonus': scoring_breakdown.get('domain_bonus', 0),
        'priority_bonus': scoring_breakdown.get('priority_bonus', 0),
        'negative_penalty': abs(scoring_breakdown.get('negative_penalty', 0)),
        
        # Platform commitment signals
        'ms_commitment_count': len(scoring_breakdown.get('microsoft_commitment_signals', [])),
        'platform_lockin_count': len(scoring_breakdown.get('platform_lockin_signals', [])),
        'open_signals_count': len(scoring_breakdown.get('open_procurement_signals', [])),
        'openness_signals_count': len(scoring_breakdown.get('platform_openness_signals', [])),
        
        # Procurement status (one-hot)
        'status_open': 1 if scoring_breakdown.get('procurement_status') == 'open' else 0,
        'status_locked': 1 if 'locked' in str(scoring_breakdown.get('procurement_status', '')) else 0,
        'status_conditional': 1 if 'conditional' in str(scoring_breakdown.get('procurement_status', '')) else 0,
        
        # Priority level (ordinal)
        'priority_high': 1 if scoring_breakdown.get('priority') == 'HIGH' else 0,
        'priority_medium': 1 if scoring_breakdown.get('priority') == 'MEDIUM' else 0,
        'priority_strategic': 1 if scoring_breakdown.get('priority') == 'STRATEGIC' else 0,
        
        # Text length features
        'title_word_count': len(title.split()),
        'text_word_count': len(text.split()) if text else 0,
        
        # Requires qualification flag
        'requires_qualification': 1 if scoring_breakdown.get('requires_qualification') else 0,
    }
    
    return features


def compute_semantic_similarity(title: str, text: str = "") -> float:
    """
    Compute semantic similarity to golden tenders (saved/favorited).
    
    Returns similarity score 0-1 (0 = no similarity, 1 = identical)
    """
    global _golden_embeddings
    
    model = get_sentence_model()
    if model is None:
        return 0.0
    
    # Load golden embeddings
    if _golden_embeddings is None:
        _load_golden_embeddings()
    
    if _golden_embeddings is None or len(_golden_embeddings) == 0:
        # No golden tenders yet, use ideal profile similarity
        return _compute_ideal_similarity(title, text)
    
    try:
        # Encode new tender
        tender_text = f"{title} {text}".strip()
        tender_embedding = model.encode(tender_text, convert_to_tensor=False)
        
        # Compute similarity to all golden tenders
        similarities = np.dot(_golden_embeddings, tender_embedding) / (
            np.linalg.norm(_golden_embeddings, axis=1) * np.linalg.norm(tender_embedding)
        )
        
        # Return max similarity (most similar golden tender)
        max_sim = float(np.max(similarities))
        
        # Also consider average similarity to top 3
        top_3_avg = float(np.mean(np.sort(similarities)[-3:]))
        
        # Blend: 70% max, 30% top-3 average
        return max_sim * 0.7 + top_3_avg * 0.3
        
    except Exception as e:
        logger.error(f"Semantic similarity error: {e}")
        return 0.0


def _compute_ideal_similarity(title: str, text: str = "") -> float:
    """Fallback: compute similarity to ideal tender profile"""
    model = get_sentence_model()
    if model is None:
        return 0.0
    
    try:
        from app.ai_scoring import get_ideal_embedding
        ideal = get_ideal_embedding()
        if ideal is None:
            return 0.0
        
        tender_text = f"{title} {text}".strip()
        tender_embedding = model.encode(tender_text, convert_to_tensor=False)
        
        similarity = np.dot(ideal, tender_embedding) / (
            np.linalg.norm(ideal) * np.linalg.norm(tender_embedding)
        )
        return float(similarity)
        
    except Exception as e:
        logger.error(f"Ideal similarity error: {e}")
        return 0.0


def _load_golden_embeddings():
    """Load pre-computed golden embeddings from disk"""
    global _golden_embeddings, _golden_titles
    
    if os.path.exists(GOLDEN_EMBEDDINGS_PATH):
        try:
            with open(GOLDEN_EMBEDDINGS_PATH, 'rb') as f:
                data = pickle.load(f)
                _golden_embeddings = data.get('embeddings')
                _golden_titles = data.get('titles', [])
                logger.info(f"âœ… Loaded {len(_golden_titles)} golden embeddings")
        except Exception as e:
            logger.error(f"Failed to load golden embeddings: {e}")
            _golden_embeddings = np.array([])
            _golden_titles = []
    else:
        _golden_embeddings = np.array([])
        _golden_titles = []


def update_golden_embeddings():
    """
    Update golden embeddings from saved/favorited tenders.
    Call this after user saves or favorites a tender.
    """
    global _golden_embeddings, _golden_titles
    
    model = get_sentence_model()
    if model is None:
        logger.warning("Cannot update golden embeddings - model not available")
        return False
    
    try:
        from app import create_app
        from app.models import TenderResult
        
        app = create_app(start_scheduler=False)
        with app.app_context():
            # Get saved and favorited tenders
            golden_tenders = TenderResult.query.filter(
                (TenderResult.saved == True) | (TenderResult.favorite == True)
            ).all()
            
            if not golden_tenders:
                logger.info("No golden tenders found")
                return False
            
            # Extract titles
            titles = [t.title for t in golden_tenders]
            
            # Compute embeddings
            embeddings = model.encode(titles, convert_to_tensor=False)
            
            # Save to disk
            _ensure_model_dir()
            with open(GOLDEN_EMBEDDINGS_PATH, 'wb') as f:
                pickle.dump({
                    'embeddings': embeddings,
                    'titles': titles,
                    'updated_at': datetime.utcnow().isoformat()
                }, f)
            
            # Update global cache
            _golden_embeddings = embeddings
            _golden_titles = titles
            
            logger.info(f"âœ… Updated golden embeddings: {len(titles)} tenders")
            return True
            
    except Exception as e:
        logger.error(f"Failed to update golden embeddings: {e}")
        return False


def train_ranker_model(min_samples: int = 10):
    """
    Train LightGBM ranker on user feedback.
    
    Labels:
    - 2: Favorited tenders (highest value)
    - 1: Saved tenders
    - 0: Old tenders not saved (implicit negative)
    
    Args:
        min_samples: Minimum positive samples required to train
    
    Returns:
        (success: bool, message: str)
    """
    try:
        import lightgbm as lgb
    except ImportError:
        return False, "LightGBM not installed. Run: pip install lightgbm"
    
    try:
        from app import create_app
        from app.models import TenderResult
        from app.scoring import score_text
        
        app = create_app(start_scheduler=False)
        with app.app_context():
            # Get all tenders
            all_tenders = TenderResult.query.all()
            
            if len(all_tenders) < min_samples:
                return False, f"Need at least {min_samples} tenders to train"
            
            # Separate by label
            favorites = [t for t in all_tenders if t.favorite]
            saved = [t for t in all_tenders if t.saved and not t.favorite]
            
            positive_count = len(favorites) + len(saved)
            if positive_count < 5:
                return False, f"Need at least 5 saved/favorited tenders. Have: {positive_count}"
            
            # Create training data
            X = []
            y = []
            
            for tender in all_tenders:
                # Get scoring breakdown
                _, _, breakdown_json = score_text(tender.title, tender.title)
                breakdown = json.loads(breakdown_json)
                
                # Extract features
                features = extract_features(tender.title, tender.title, breakdown)
                
                # Add semantic similarity as feature
                features['semantic_similarity'] = compute_semantic_similarity(tender.title)
                
                # Convert to array
                feature_values = list(features.values())
                X.append(feature_values)
                
                # Label
                if tender.favorite:
                    y.append(2)
                elif tender.saved:
                    y.append(1)
                else:
                    y.append(0)
            
            X = np.array(X)
            y = np.array(y)
            
            # Get feature names for importance
            feature_names = list(features.keys())
            
            # Train LightGBM
            model = lgb.LGBMClassifier(
                n_estimators=50,
                max_depth=4,
                min_child_samples=3,
                learning_rate=0.1,
                class_weight='balanced',  # Handle imbalanced labels
                verbose=-1,
            )
            
            model.fit(X, y)
            
            # Save model
            _ensure_model_dir()
            with open(RANKER_MODEL_PATH, 'wb') as f:
                pickle.dump({
                    'model': model,
                    'feature_names': feature_names,
                    'trained_at': datetime.utcnow().isoformat(),
                    'sample_count': len(y),
                    'positive_count': positive_count,
                }, f)
            
            # Update global
            global _ranker_model
            _ranker_model = model
            
            # Get feature importance
            importance = dict(zip(feature_names, model.feature_importances_))
            top_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:5]
            
            logger.info(f"âœ… Trained ranker on {len(y)} samples ({positive_count} positive)")
            logger.info(f"Top features: {top_features}")
            
            return True, f"Trained on {len(y)} tenders. Top features: {[f[0] for f in top_features]}"
            
    except Exception as e:
        logger.error(f"Training failed: {e}")
        return False, f"Training error: {str(e)}"


def load_ranker_model():
    """Load trained ranker model from disk"""
    global _ranker_model
    
    if _ranker_model is not None:
        return _ranker_model
    
    if os.path.exists(RANKER_MODEL_PATH):
        try:
            with open(RANKER_MODEL_PATH, 'rb') as f:
                data = pickle.load(f)
                _ranker_model = data['model']
                logger.info(f"âœ… Loaded ranker model (trained on {data['sample_count']} samples)")
                return _ranker_model
        except Exception as e:
            logger.error(f"Failed to load ranker model: {e}")
    
    return None


def ml_score(title: str, text: str = "", scoring_breakdown: dict = None) -> dict:
    """
    Get ML-enhanced score for a tender.
    
    Returns dict with:
    - ml_score: 0-100 ML-predicted relevance
    - keyword_score: Original keyword-based score
    - semantic_score: Similarity to golden tenders
    - final_score: Blended score
    - explanation: Human-readable explanation
    - feature_importance: Which features drove the score
    """
    import json
    from app.scoring import score_text
    
    # Get keyword score and breakdown
    if scoring_breakdown is None:
        keyword_score, matched, breakdown_json = score_text(title, text)
        scoring_breakdown = json.loads(breakdown_json)
    else:
        keyword_score = scoring_breakdown.get('normalized_score', 5)
        matched = scoring_breakdown.get('matched_keywords', [])
    
    # Handle excluded tenders
    if scoring_breakdown.get('excluded'):
        return {
            'ml_score': 0,
            'keyword_score': 0,
            'semantic_score': 0,
            'final_score': 0,
            'explanation': scoring_breakdown.get('exclusion_reason', 'Excluded'),
            'feature_importance': {},
            'method': 'excluded',
        }
    
    # Extract features
    features = extract_features(title, text, scoring_breakdown)
    
    # Compute semantic similarity
    semantic_sim = compute_semantic_similarity(title, text)
    features['semantic_similarity'] = semantic_sim
    
    # Convert similarity to 0-100 scale
    semantic_score = max(0, min(100, semantic_sim * 100))
    
    # Try ML model prediction
    ranker = load_ranker_model()
    ml_score_val = None
    feature_importance = {}
    
    if ranker is not None:
        try:
            feature_values = np.array([list(features.values())])
            
            # Get class probabilities
            probs = ranker.predict_proba(feature_values)[0]
            
            # Score = weighted sum: 0*P(0) + 50*P(1) + 100*P(2)
            ml_score_val = probs[0] * 0 + probs[1] * 50 + probs[2] * 100
            
            # Get feature importance for this prediction
            importance = dict(zip(features.keys(), ranker.feature_importances_))
            feature_importance = {k: round(v * 100, 1) for k, v in 
                                  sorted(importance.items(), key=lambda x: x[1], reverse=True)[:5]}
            
        except Exception as e:
            logger.error(f"ML prediction error: {e}")
    
    # Compute final blended score
    if ml_score_val is not None:
        # Have ML model: 50% ML, 30% keyword, 20% semantic
        final_score = ml_score_val * 0.5 + keyword_score * 0.3 + semantic_score * 0.2
        method = 'ml_hybrid'
    elif semantic_sim > 0:
        # No ML model but have semantic: 60% keyword, 40% semantic
        final_score = keyword_score * 0.6 + semantic_score * 0.4
        method = 'semantic_hybrid'
    else:
        # Fallback to keyword only
        final_score = keyword_score
        method = 'keyword_only'
    
    final_score = round(max(0, min(100, final_score)), 1)
    
    # Generate explanation
    explanation = _generate_explanation(features, scoring_breakdown, semantic_sim, ml_score_val)
    
    return {
        'ml_score': round(ml_score_val, 1) if ml_score_val else None,
        'keyword_score': round(keyword_score, 1),
        'semantic_score': round(semantic_score, 1),
        'final_score': final_score,
        'explanation': explanation,
        'feature_importance': feature_importance,
        'method': method,
        'features': features,
    }


def _generate_explanation(features: dict, breakdown: dict, semantic_sim: float, ml_score: float) -> str:
    """Generate human-readable explanation for the score"""
    parts = []
    
    # Domain matches
    domains = breakdown.get('domains_matched', [])
    if domains:
        parts.append(f"Matches F2 domains: {', '.join(domains)}")
    
    # Semantic similarity
    if semantic_sim > 0.7:
        parts.append("Very similar to your saved tenders")
    elif semantic_sim > 0.5:
        parts.append("Somewhat similar to your saved tenders")
    
    # Platform commitment
    if features.get('ms_commitment_count', 0) > 0:
        if features.get('openness_signals_count', 0) > 0:
            parts.append("Microsoft mentioned but may be open to alternatives")
        else:
            parts.append("âš ï¸ Microsoft platform appears mandated - requires qualification")
    
    # Priority
    if features.get('priority_strategic'):
        parts.append("ðŸŽ¯ HIGH STRATEGIC VALUE opportunity")
    elif features.get('priority_high'):
        parts.append("High priority match")
    
    # ML confidence
    if ml_score is not None:
        if ml_score > 70:
            parts.append("ML model predicts high relevance based on your feedback")
        elif ml_score < 30:
            parts.append("ML model predicts low relevance based on your feedback")
    
    return " | ".join(parts) if parts else "Basic keyword match"


def get_model_status() -> dict:
    """Get status of ML models"""
    sentence_model = get_sentence_model()
    ranker = load_ranker_model()
    
    # Check golden embeddings
    global _golden_embeddings, _golden_titles
    if _golden_embeddings is None:
        _load_golden_embeddings()
    
    status = {
        'sentence_model_loaded': sentence_model is not None,
        'ranker_model_loaded': ranker is not None,
        'golden_tenders_count': len(_golden_titles) if _golden_titles else 0,
    }
    
    # Add ranker details if available
    if os.path.exists(RANKER_MODEL_PATH):
        try:
            with open(RANKER_MODEL_PATH, 'rb') as f:
                data = pickle.load(f)
                status['ranker_trained_at'] = data.get('trained_at')
                status['ranker_sample_count'] = data.get('sample_count')
                status['ranker_positive_count'] = data.get('positive_count')
        except:
            pass
    
    return status

