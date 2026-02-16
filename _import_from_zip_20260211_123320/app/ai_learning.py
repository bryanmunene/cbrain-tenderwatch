"""
Adaptive learning system that improves scoring based on user feedback
Learns from saved/favorited tenders to personalize relevance
"""

import pickle
import logging
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Tuple

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent.parent / 'models'
MODEL_DIR.mkdir(exist_ok=True)

MODEL_PATH = MODEL_DIR / 'learning_model.pkl'
SCALER_PATH = MODEL_DIR / 'scaler.pkl'

def extract_features(tender_data: dict) -> np.array:
    """
    Extract numerical features from tender for ML model
    
    Features:
    - Score (semantic + keyword)
    - Title length
    - Description length (words)
    - Number of keywords matched
    - Source bias value
    - Category confidence
    - Has budget (0/1)
    - Has deadline (0/1)
    - Days old
    """
    features = []
    
    # Core scores
    features.append(tender_data.get('score', 0))
    features.append(tender_data.get('semantic_score', 0))
    features.append(tender_data.get('keyword_score', 0))
    
    # Text features
    title = tender_data.get('title', '')
    description = tender_data.get('description', '')
    features.append(len(title))
    features.append(len(description.split()))
    features.append(tender_data.get('keywords_count', 0))
    
    # Metadata features
    features.append(tender_data.get('source_bias', 0))
    features.append(tender_data.get('confidence', 0))
    features.append(1 if tender_data.get('budget') else 0)
    features.append(1 if tender_data.get('deadline') else 0)
    
    # Recency (days since created)
    created = tender_data.get('created_at')
    if created:
        if isinstance(created, str):
            created = datetime.fromisoformat(created.replace('Z', '+00:00'))
        days_old = (datetime.now() - created).days
        features.append(days_old)
    else:
        features.append(0)
    
    return np.array(features).reshape(1, -1)

class AdaptiveLearner:
    """Machine learning system that learns from user interactions"""
    
    def __init__(self):
        self.model = None
        self.scaler = None
        self.last_trained = None
        self.training_size = 0
        
    def load_model(self):
        """Load existing model from disk"""
        try:
            if MODEL_PATH.exists() and SCALER_PATH.exists():
                with open(MODEL_PATH, 'rb') as f:
                    self.model = pickle.load(f)
                with open(SCALER_PATH, 'rb') as f:
                    self.scaler = pickle.load(f)
                logger.info("âœ… Loaded existing learning model")
                return True
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
        return False
    
    def save_model(self):
        """Save trained model to disk"""
        try:
            with open(MODEL_PATH, 'wb') as f:
                pickle.dump(self.model, f)
            with open(SCALER_PATH, 'wb') as f:
                pickle.dump(self.scaler, f)
            logger.info("âœ… Saved learning model")
        except Exception as e:
            logger.error(f"Failed to save model: {e}")
    
    def train(self, positive_samples: List[dict], negative_samples: List[dict]):
        """
        Train model on user feedback
        
        Args:
            positive_samples: List of tender data for saved/favorited tenders
            negative_samples: List of tender data for dismissed/low-scored tenders
        """
        if len(positive_samples) < 5:
            logger.info("âš ï¸ Not enough positive samples to train (need at least 5)")
            return False
        
        try:
            # Extract features
            X_pos = np.vstack([extract_features(t) for t in positive_samples])
            X_neg = np.vstack([extract_features(t) for t in negative_samples])
            
            X = np.vstack([X_pos, X_neg])
            y = np.array([1] * len(X_pos) + [0] * len(X_neg))
            
            # Scale features
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            
            # Train Random Forest classifier
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                random_state=42
            )
            self.model.fit(X_scaled, y)
            
            # Save model
            self.save_model()
            self.last_trained = datetime.now()
            self.training_size = len(X)
            
            logger.info(f"âœ… Model trained on {len(X)} samples ({len(X_pos)} positive, {len(X_neg)} negative)")
            return True
            
        except Exception as e:
            logger.error(f"Training failed: {e}")
            return False
    
    def predict_relevance(self, tender_data: dict) -> Tuple[float, float]:
        """
        Predict relevance score for a tender
        
        Returns:
            (probability, confidence) - probability of being relevant (0-1), confidence in prediction
        """
        if self.model is None:
            if not self.load_model():
                return 0.5, 0.0  # No model available, return neutral
        
        try:
            features = extract_features(tender_data)
            features_scaled = self.scaler.transform(features)
            
            # Get probability of being relevant
            proba = self.model.predict_proba(features_scaled)[0][1]
            
            # Confidence based on how decisive the prediction is
            confidence = abs(proba - 0.5) * 2  # 0.5 = uncertain, 0 or 1 = confident
            
            return proba, confidence
            
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return 0.5, 0.0
    
    def adjust_score(self, original_score: float, tender_data: dict) -> float:
        """
        Adjust original score based on learned preferences
        
        Returns:
            Adjusted score (0-100)
        """
        proba, confidence = self.predict_relevance(tender_data)
        
        # Only adjust if model is confident
        if confidence < 0.3:
            return original_score
        
        # Blend original score with learned preference
        ai_score = proba * 100
        weight = confidence  # More confident = more weight on AI
        
        adjusted = original_score * (1 - weight) + ai_score * weight
        return round(adjusted, 2)
    
    def get_feature_importance(self) -> dict:
        """Get which features matter most for relevance"""
        if self.model is None:
            return {}
        
        feature_names = [
            'score', 'semantic_score', 'keyword_score',
            'title_length', 'description_length', 'keywords_count',
            'source_bias', 'confidence', 'has_budget', 'has_deadline', 'days_old'
        ]
        
        importances = self.model.feature_importances_
        return dict(zip(feature_names, importances))

# Global learner instance
_learner = None

def get_learner() -> AdaptiveLearner:
    """Get singleton learner instance"""
    global _learner
    if _learner is None:
        _learner = AdaptiveLearner()
        _learner.load_model()
    return _learner

def train_from_database():
    """Train model using data from database"""
    try:
        from app.models import TenderResult
        from app import create_app
        
        app = create_app(start_scheduler=False)
        with app.app_context():
            # Get positive examples (saved or favorited)
            positive = TenderResult.query.filter(
                (TenderResult.saved == True) | (TenderResult.favorite == True)
            ).all()
            
            # Get negative examples (low scores, not saved)
            negative = TenderResult.query.filter(
                TenderResult.score < 30,
                TenderResult.saved == False,
                TenderResult.favorite == False
            ).limit(len(positive) * 2).all()  # 2x negative samples
            
            if len(positive) < 5:
                logger.info(f"Not enough training data yet ({len(positive)} saved tenders)")
                return False
            
            # Convert to feature dicts
            pos_data = [tender_to_dict(t) for t in positive]
            neg_data = [tender_to_dict(t) for t in negative]
            
            # Train
            learner = get_learner()
            return learner.train(pos_data, neg_data)
            
    except Exception as e:
        logger.error(f"Failed to train from database: {e}")
        return False

def tender_to_dict(tender) -> dict:
    """Convert TenderResult model to feature dict"""
    breakdown = {}
    if tender.scoring_breakdown:
        try:
            breakdown = json.loads(tender.scoring_breakdown)
        except:
            pass
    
    return {
        'score': tender.score,
        'semantic_score': breakdown.get('semantic_score', tender.score),
        'keyword_score': breakdown.get('keyword_score', tender.score),
        'title': tender.title,
        'description': tender.description or '',
        'keywords_count': breakdown.get('keywords_found', 0),
        'source_bias': 0,  # Could extract from breakdown
        'confidence': tender.confidence or 0.5,
        'budget': None,  # Could extract from entities
        'deadline': tender.deadline,
        'created_at': tender.created_at
    }

