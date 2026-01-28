from flask import Blueprint, render_template, request, redirect, url_for, jsonify
import json
from datetime import datetime, timedelta

from app.extensions import db
from app.models import TenderSource, TenderResult, AppSettings
from app.scraper import run_scan
from app.translator import translate_to_english, detect_language


main = Blueprint("main", __name__)


@main.route("/api/source-status")
def source_status():
    """API endpoint to check which sources are active and how many tenders they've contributed"""
    sources = TenderSource.query.all()
    status = []
    
    for source in sources:
        tender_count = TenderResult.query.filter_by(source_id=source.id).count()
        status.append({
            "id": source.id,
            "name": source.name,
            "url": source.url,
            "active": source.active,
            "tender_count": tender_count,
            "favorite": source.favorite
        })
    
    return jsonify(status)


@main.route("/")
def dashboard():
    """Dashboard with statistics and overview"""
    # Filter tenders from last month only
    one_month_ago = datetime.utcnow() - timedelta(days=30)
    
    total_tenders = TenderResult.query.filter(TenderResult.created_at >= one_month_ago).count()
    high_score_count = TenderResult.query.filter(
        TenderResult.score >= 70,
        TenderResult.created_at >= one_month_ago
    ).count()
    saved_count = TenderResult.query.filter_by(saved=True).filter(
        TenderResult.created_at >= one_month_ago
    ).count()
    favorite_count = TenderResult.query.filter_by(favorite=True).filter(
        TenderResult.created_at >= one_month_ago
    ).count()
    active_sources = TenderSource.query.filter_by(active=True).count()
    
    # Get source contribution breakdown
    source_contributions = db.session.query(
        TenderSource.name,
        db.func.count(TenderResult.id).label('count')
    ).outerjoin(TenderResult).group_by(TenderSource.name).all()
    
    # Get category breakdown (last month only)
    categories = db.session.query(
        TenderResult.category,
        db.func.count(TenderResult.id).label('count')
    ).filter(TenderResult.created_at >= one_month_ago).group_by(TenderResult.category).all()
    
    # Get recent tenders (last month only)
    recent_tenders = TenderResult.query.filter(
        TenderResult.created_at >= one_month_ago
    ).order_by(TenderResult.created_at.desc()).limit(10).all()
    
    return render_template(
        "dashboard.html",
        total_tenders=total_tenders,
        high_score_count=high_score_count,
        saved_count=saved_count,
        favorite_count=favorite_count,
        active_sources=active_sources,
        source_contributions=source_contributions,
        categories=categories,
        recent_tenders=recent_tenders,
    )


@main.route("/scan", methods=["GET", "POST"])
def scan():
    if request.method == "POST":
        from app.notifications import notify_new_tenders
        
        # Get before count
        before_count = TenderResult.query.count()
        
        # Run scan
        new_tenders = run_scan()
        
        # Check for unnotified tenders and send notifications
        unnotified = TenderResult.query.filter_by(notified=False).all()
        if unnotified:
            notify_new_tenders(unnotified)
            for tender in unnotified:
                tender.notified = True
            db.session.commit()
        
        return redirect(url_for("main.scan"))

    # Get filtering and sorting parameters
    sort_by = request.args.get("sort", "score")
    category = request.args.get("category", "")
    min_score = request.args.get("min_score", "0")
    search = request.args.get("search", "").strip()
    
    try:
        min_score = float(min_score)
    except (ValueError, TypeError):
        min_score = 0
    
    # Build query - filter by date (last month only)
    one_month_ago = datetime.utcnow() - timedelta(days=30)
    query = TenderResult.query.filter(TenderResult.created_at >= one_month_ago)
    
    if category:
        query = query.filter_by(category=category)
    
    if min_score > 0:
        query = query.filter(TenderResult.score >= min_score)
    
    if search:
        query = query.filter(
            db.or_(
                TenderResult.title.ilike(f"%{search}%"),
                TenderResult.description.ilike(f"%{search}%"),
                TenderResult.buyer.ilike(f"%{search}%")
            )
        )
    
    results = query.order_by(TenderResult.created_at.desc()).all()
    
    # Sort results
    if sort_by == "score":
        results = sorted(results, key=lambda x: x.score or 0, reverse=True)
    elif sort_by == "deadline":
        results = sorted(results, key=lambda x: x.deadline or "", reverse=False)
    elif sort_by == "newest":
        results = sorted(results, key=lambda x: x.created_at, reverse=True)

    # Get categories for filter dropdown
    categories = db.session.query(TenderResult.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    
    return render_template(
        "scan_results.html",
        results=results,
        sort_by=sort_by,
        category=category,
        min_score=min_score,
        search=search,
        categories=categories,
    )


@main.route("/tender/<int:tid>")
def tender_detail(tid):
    """View detailed information about a tender including scoring breakdown"""
    r = TenderResult.query.get_or_404(tid)
    # Auto-translate if needed
    if r.title and (not r.title_translated or r.title_translated == r.title):
        lang = detect_language(r.title)
        if lang != "en":
            r.title_translated = translate_to_english(r.title)
            db.session.commit()
    # Parse scoring breakdown
    scoring_info = {}
    if r.scoring_breakdown:
        try:
            scoring_info = json.loads(r.scoring_breakdown)
        except:
            scoring_info = {}
    return render_template("tender_detail.html", tender=r, scoring_info=scoring_info)

# --- scan function starts here ---
## Duplicate scan function removed. Only one scan function should exist.


@main.route("/source/<int:sid>/toggle", methods=["POST"])
def toggle_source_active(sid):
    """Toggle active status for a source"""
    s = TenderSource.query.get_or_404(sid)
    s.active = not s.active
    db.session.commit()
    return redirect(request.referrer or url_for("main.sources"))


@main.route("/source/<int:sid>/favorite", methods=["POST"])
def toggle_source_favorite(sid):
    """Toggle favorite status for a source"""
    s = TenderSource.query.get_or_404(sid)
    s.favorite = not s.favorite
    db.session.commit()
    return redirect(request.referrer or url_for("main.sources"))


@main.route("/source/<int:sid>/delete", methods=["POST"])
def delete_source(sid):
    """Delete a source"""
    s = TenderSource.query.get_or_404(sid)
    db.session.delete(s)
    db.session.commit()
    return redirect(url_for("main.sources"))


@main.route("/sources", methods=["GET", "POST"])
def sources():
    """View and manage tender sources"""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        url = request.form.get("url", "").strip()
        
        if not name or not url:
            active_sources = TenderSource.query.filter_by(active=True).all()
            inactive_sources = TenderSource.query.filter_by(active=False).all()
            return render_template(
                "sources.html",
                active_sources=active_sources,
                inactive_sources=inactive_sources,
                error="Name and URL are required"
            ), 400
        
        # Check if source already exists
        if TenderSource.query.filter_by(url=url).first():
            active_sources = TenderSource.query.filter_by(active=True).all()
            inactive_sources = TenderSource.query.filter_by(active=False).all()
            return render_template(
                "sources.html",
                active_sources=active_sources,
                inactive_sources=inactive_sources,
                error="This source URL already exists"
            ), 400
        
        # Create new source
        new_source = TenderSource(name=name, url=url, active=True)
        db.session.add(new_source)
        db.session.commit()
        
        return redirect(url_for("main.sources"))
    
    active_sources = TenderSource.query.filter_by(active=True).all()
    inactive_sources = TenderSource.query.filter_by(active=False).all()
    
    return render_template(
        "sources.html",
        active_sources=active_sources,
        inactive_sources=inactive_sources
    )


@main.route("/saved")
def saved():
    results = (
        TenderResult.query
        .filter_by(saved=True)
        .order_by(TenderResult.created_at.desc())
        .all()
    )
    return render_template("scan_results.html", results=results, title="Saved Tenders")


@main.route("/favorites")
def favorites():
    """View favorite tenders"""
    results = (
        TenderResult.query
        .filter_by(favorite=True)
        .order_by(TenderResult.score.desc(), TenderResult.created_at.desc())
        .all()
    )
    return render_template("scan_results.html", results=results, title="Favorite Tenders")


@main.route("/save/<int:rid>", methods=["POST"])
def save(rid):
    r = TenderResult.query.get_or_404(rid)
    r.saved = True
    db.session.commit()
    return redirect(request.referrer or url_for("main.scan"))


@main.route("/unsave/<int:rid>", methods=["POST"])
def unsave(rid):
    r = TenderResult.query.get_or_404(rid)
    r.saved = False
    db.session.commit()
    return redirect(request.referrer or url_for("main.scan"))


@main.route("/tender/<int:rid>/favorite", methods=["POST"])
def toggle_favorite(rid):
    """Toggle favorite status for a tender"""
    r = TenderResult.query.get_or_404(rid)
    r.favorite = not r.favorite
    db.session.commit()
    return redirect(request.referrer or url_for("main.scan"))


@main.route("/settings", methods=["GET", "POST"])
def settings():
    """View and update app settings"""
    settings = AppSettings.query.first()
    if not settings:
        settings = AppSettings()
        db.session.add(settings)
        db.session.commit()
    
    if request.method == "POST":
        # Update scheduler settings
        settings.auto_scan_enabled = request.form.get("auto_scan_enabled") == "on"
        settings.scan_interval_minutes = int(request.form.get("scan_interval_minutes", 60))
        
        # Update notification settings
        settings.notifications_enabled = request.form.get("notifications_enabled") == "on"
        settings.notify_desktop = request.form.get("notify_desktop") == "on"
        settings.notify_email = request.form.get("notify_email") == "on"
        settings.min_score_to_notify = float(request.form.get("min_score_to_notify", 50.0))
        
        # Update email settings
        settings.email_recipients = request.form.get("email_recipients", "").strip()
        settings.smtp_server = request.form.get("smtp_server", "smtp.gmail.com").strip()
        settings.smtp_port = int(request.form.get("smtp_port", 587))
        settings.smtp_username = request.form.get("smtp_username", "").strip()
        
        # Only update password if provided
        smtp_password = request.form.get("smtp_password", "").strip()
        if smtp_password:
            settings.smtp_password = smtp_password
        
        db.session.commit()
        
        # Restart scheduler with new settings
        from app.scheduler import restart_scheduler
        from flask import current_app
        restart_scheduler(current_app._get_current_object())
        
        return redirect(url_for("main.settings"))
    
    from app.scheduler import get_scheduler_status
    scheduler_status = get_scheduler_status()
    
    return render_template(
        "settings.html",
        settings=settings,
        scheduler_status=scheduler_status
    )


@main.route("/test-notification", methods=["POST"])
def test_notification():
    """Send a test notification"""
    from app.notifications import send_desktop_notification
    
    send_desktop_notification(
        "TenderWatch Test",
        "This is a test notification from TenderWatch!"
    )
    
    return jsonify({"success": True, "message": "Test notification sent"})


from app.translator import translate_to_english, detect_language

# ...existing code...

# Ensure auto-translation in tender detail view
## Duplicate tender_detail removed; see earlier definition for logic.

# Ensure auto-translation in scan results view
## Duplicate scan removed; see earlier definition for logic.
