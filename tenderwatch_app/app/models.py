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
    
    score = db.Column(db.Float)
    keywords_matched = db.Column(db.Text)
    scoring_breakdown = db.Column(db.Text, default="")

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
