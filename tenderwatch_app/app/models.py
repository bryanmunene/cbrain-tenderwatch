from datetime import datetime
from app.extensions import db

class TenderSource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    active = db.Column(db.Boolean, default=True)
    favorite = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class TenderResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.Text, nullable=False)
    title_translated = db.Column(db.Text, default="")
    link = db.Column(db.Text, unique=True, nullable=False)
    description = db.Column(db.Text, default="")
    description_translated = db.Column(db.Text, default="")

    buyer = db.Column(db.String(200))
    country = db.Column(db.String(200))
    deadline = db.Column(db.String(200))
    publication_date = db.Column(db.String(200))  # F2: for timing filter
    
    score = db.Column(db.Float)
    keywords_matched = db.Column(db.Text)
    scoring_breakdown = db.Column(db.Text, default="")
    
    # F2-ALIGNED CLASSIFICATION FIELDS
    inferred_domains = db.Column(db.Text, default="")  # JSON: ["EDMS", "Workflow", "Gov"]
    priority_level = db.Column(db.String(20), default="LOW")  # HIGH, MEDIUM, LOW, LOCKED, CONDITIONAL, STRATEGIC
    likely_fit_for_f2 = db.Column(db.String(20), default="uncertain")  # true, false, uncertain, no-go, discuss, conditional, strategic
    timing_status = db.Column(db.String(100), default="")  # Timing constraint result
    procurement_status = db.Column(db.String(30), default="open")  # open, locked, locked_but_open, conditional_nogo, conditional_strategic
    
    # Platform commitment qualification fields
    requires_qualification = db.Column(db.Boolean, default=False)  # True if Microsoft-mandated
    qualification_reason = db.Column(db.Text, default="")  # Why qualification is needed
    qualification_answers = db.Column(db.Text, default="")  # JSON: user-provided answers to qualification questions
    platform_commitment_signals = db.Column(db.Text, default="")  # JSON: detected Microsoft commitment signals
    
    # Discovery metadata
    discovery_method = db.Column(db.String(50), default="manual")  # 'manual', 'auto', 'priority'
    search_query = db.Column(db.String(500))  # Search query that found this (for auto-discovered)
    search_source = db.Column(db.String(50))  # 'google', 'bing', or source name

    # AI-enhanced fields
    semantic_score = db.Column(db.Float, default=0.0)
    ai_confidence = db.Column(db.Float, default=0.0)
    entities_extracted = db.Column(db.Text, default="")  # JSON with extracted entities
    ai_summary = db.Column(db.Text, default="")  # AI-generated summary
    
    saved = db.Column(db.Boolean, default=False)
    favorite = db.Column(db.Boolean, default=False)
    notified = db.Column(db.Boolean, default=False)

    source_id = db.Column(db.Integer, db.ForeignKey("tender_source.id"))
    source = db.relationship("TenderSource")
    
    category = db.Column(db.String(100))
    confidence = db.Column(db.Float)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
class LearnedKeyword(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    keyword = db.Column(db.String(100), unique=True, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    weight = db.Column(db.Float, default=1.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AppSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # Scheduler settings
    auto_scan_enabled = db.Column(db.Boolean, default=False)
    scan_interval_minutes = db.Column(db.Integer, default=60)
    
    # Auto-discovery settings
    auto_discovery_enabled = db.Column(db.Boolean, default=False)
    google_api_key = db.Column(db.String(500), default="")
    google_cx = db.Column(db.String(500), default="")  # Custom Search Engine ID
    bing_api_key = db.Column(db.String(500), default="")
    discovery_queries = db.Column(db.Text, default="")  # JSON list of custom queries
    results_per_query = db.Column(db.Integer, default=10)  # Results to fetch per query
    
    # AI/ML settings
    ai_scoring_enabled = db.Column(db.Boolean, default=True)
    ai_learning_enabled = db.Column(db.Boolean, default=True)
    entity_extraction_enabled = db.Column(db.Boolean, default=True)
    
    # Notification settings
    notifications_enabled = db.Column(db.Boolean, default=True)
    notify_desktop = db.Column(db.Boolean, default=True)
    notify_email = db.Column(db.Boolean, default=False)
    
    # Email settings
    email_recipients = db.Column(db.Text, default="")  # Comma-separated
    smtp_server = db.Column(db.String(200), default="smtp.gmail.com")
    smtp_port = db.Column(db.Integer, default=587)
    smtp_username = db.Column(db.String(200), default="")
    smtp_password = db.Column(db.String(200), default="")
    
    # Notification thresholds
    min_score_to_notify = db.Column(db.Float, default=50.0)
    
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PushSubscription(db.Model):
    """Store user push notification subscriptions"""
    id = db.Column(db.Integer, primary_key=True)
    endpoint = db.Column(db.Text, unique=True, nullable=False)
    p256dh_key = db.Column(db.Text, nullable=False)  # Client public key
    auth_key = db.Column(db.Text, nullable=False)    # Client authentication secret
    user_agent = db.Column(db.Text, default="")
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used = db.Column(db.DateTime, default=datetime.utcnow)


class DiscoveryLog(db.Model):
    """Track auto-discovery runs and statistics"""
    id = db.Column(db.Integer, primary_key=True)
    run_type = db.Column(db.String(50), nullable=False)  # 'manual', 'scheduled'
    queries_run = db.Column(db.Integer, default=0)
    results_found = db.Column(db.Integer, default=0)
    results_saved = db.Column(db.Integer, default=0)  # Results that passed scoring threshold
    google_quota_used = db.Column(db.Integer, default=0)
    bing_quota_used = db.Column(db.Integer, default=0)
    execution_time_seconds = db.Column(db.Float, default=0.0)
    error_message = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class FeedbackEvent(db.Model):
    """User feedback signals used for relevance model training."""
    id = db.Column(db.Integer, primary_key=True)
    tender_id = db.Column(db.Integer, db.ForeignKey("tender_result.id"), nullable=False, index=True)
    tender = db.relationship("TenderResult")
    event_type = db.Column(db.String(50), nullable=False, index=True)  # view, save, unsave, favorite, unfavorite
    label_weight = db.Column(db.Float, default=0.0)  # +1 positive, -1 negative, fractional for soft signals
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
