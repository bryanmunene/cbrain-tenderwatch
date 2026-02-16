"""
AI-powered semantic scoring using sentence transformers
Provides more intelligent relevance detection than keyword matching
"""

import numpy as np
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

# Global model instance (loaded once)
_model = None

def load_model():
    """Load sentence transformer model (lazy loading)"""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            # Using lightweight model optimized for speed
            _model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("✅ Semantic scoring model loaded successfully")
        except Exception as e:
            logger.error(f"❌ Failed to load semantic model: {e}")
            _model = False  # Mark as failed to avoid retrying
    return _model if _model is not False else None

# cBrain's ideal tender profile
IDEAL_TENDER_PROFILE = """
Electronic Document Management System (EDMS) for government agencies
Case management and workflow automation software platform
Records management archives and digitization solutions
Complaint management and citizen service delivery systems
Business process management and workflow automation
Document lifecycle management and version control
Enterprise content management system implementation
Digital transformation of government services
Government portal and online service delivery platform
License and permit management system automation
"""

@lru_cache(maxsize=1)
def get_ideal_embedding():
    """Get cached embedding of ideal tender profile"""
    model = load_model()
    if model is None:
        return None
    return model.encode(IDEAL_TENDER_PROFILE, convert_to_tensor=False)

def semantic_score(title: str, description: str = "") -> tuple:
    """
    Calculate semantic similarity score using AI embeddings
    
    Args:
        title: Tender title
        description: Tender description (optional)
    
    Returns:
        (score, confidence, method) tuple:
        - score: 0-100 relevance percentage
        - confidence: 0-1 confidence in the score
        - method: 'semantic' or 'fallback'
    """
    model = load_model()
    
    if model is None:
        # Fallback to keyword-based scoring
        from app.scoring import score_text
        score, _, _ = score_text(title, description)
        return score, 0.5, 'fallback'
    
    try:
        # Combine title and description
        tender_text = f"{title} {description}".strip()
        
        if not tender_text:
            return 0, 0, 'semantic'
        
        # Get embeddings
        ideal_embedding = get_ideal_embedding()
        tender_embedding = model.encode(tender_text, convert_to_tensor=False)
        
        # Calculate cosine similarity
        similarity = np.dot(ideal_embedding, tender_embedding) / (
            np.linalg.norm(ideal_embedding) * np.linalg.norm(tender_embedding)
        )
        
        # Convert to 0-100 scale with adjusted threshold
        # 0.2 similarity = 0%, 0.6 similarity = 100%
        score = max(0, min(100, (similarity - 0.2) / 0.4 * 100))
        
        # Confidence based on text length
        text_length = len(tender_text.split())
        confidence = min(1.0, text_length / 50)  # Full confidence at 50+ words
        
        return round(score, 2), round(confidence, 2), 'semantic'
        
    except Exception as e:
        logger.error(f"Semantic scoring error: {e}")
        # Fallback to keyword scoring
        from app.scoring import score_text
        score, _, _ = score_text(title, description)
        return score, 0.5, 'fallback'

def hybrid_score(title: str, description: str = "") -> tuple:
    """
    Combine semantic and keyword scores for best results
    
    Returns:
        (final_score, breakdown_dict)
    """
    # Get both scores
    semantic_score_val, confidence, method = semantic_score(title, description)
    
    from app.scoring import score_text
    keyword_score_val, matched_keywords, keyword_breakdown = score_text(title, description)
    
    # Weight semantic score more when confident
    semantic_weight = 0.7 if confidence > 0.7 else 0.5
    keyword_weight = 1 - semantic_weight
    
    # Combine scores
    final_score = (
        semantic_score_val * semantic_weight + 
        keyword_score_val * keyword_weight
    )
    
    breakdown = {
        'final_score': round(final_score, 2),
        'semantic_score': semantic_score_val,
        'keyword_score': keyword_score_val,
        'semantic_confidence': confidence,
        'scoring_method': method,
        'matched_keywords': matched_keywords,
        'weights': {
            'semantic': semantic_weight,
            'keyword': keyword_weight
        }
    }
    
    return round(final_score, 2), matched_keywords, breakdown

def batch_score_tenders(tenders: list) -> list:
    """
    Efficiently score multiple tenders in batch
    
    Args:
        tenders: List of (title, description) tuples
    
    Returns:
        List of scores
    """
    model = load_model()
    
    if model is None or not tenders:
        return [0] * len(tenders)
    
    try:
        # Batch encode all tenders
        tender_texts = [f"{t[0]} {t[1]}".strip() for t in tenders]
        tender_embeddings = model.encode(tender_texts, convert_to_tensor=False)
        
        ideal_embedding = get_ideal_embedding()
        
        # Calculate all similarities at once
        similarities = np.dot(tender_embeddings, ideal_embedding) / (
            np.linalg.norm(tender_embeddings, axis=1) * 
            np.linalg.norm(ideal_embedding)
        )
        
        # Convert to 0-100 scale
        scores = np.maximum(0, np.minimum(100, (similarities - 0.2) / 0.4 * 100))
        
        return [round(s, 2) for s in scores]
        
    except Exception as e:
        logger.error(f"Batch scoring error: {e}")
        return [0] * len(tenders)
