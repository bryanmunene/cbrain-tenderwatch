from flask import Blueprint, render_template, request, redirect, url_for, jsonify, make_response
import json
import csv
from io import StringIO
from datetime import datetime, timedelta

from app.extensions import db
from app.models import TenderSource, TenderResult, AppSettings
from app.scraper import run_scan
from app.translator import translate_to_english, detect_language
from app.geography import recommendation_priority, shortlist_mode_match, tender_sort_key


main = Blueprint("main", __name__)
RECENT_WINDOW_OPTIONS = [7, 30, 60, 90, 180]
SHORTLIST_MODES = ["africa", "global", "combined"]
SOURCE_GROUP_OPTIONS = [
    "africa_priority",
    "africa_regional",
    "global_public",
    "global_multilateral",
    "aggregator",
    "experimental",
]


def _get_settings() -> AppSettings:
    settings = AppSettings.query.first()
    if settings:
        return settings
    settings = AppSettings()
    db.session.add(settings)
    db.session.commit()
    return settings


def _parse_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _score_breakdown(tender: TenderResult) -> dict:
    raw = getattr(tender, "scoring_breakdown", "") or ""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _shortlist_default_mode(settings: AppSettings) -> str:
    if settings.africa_only_mode:
        return "africa"
    if settings.include_global_in_default_shortlist:
        return "combined"
    return "africa"


def _apply_scan_filters(query, recent_days, category, min_score, search):
    cutoff = datetime.utcnow() - timedelta(days=recent_days)
    query = query.filter(TenderResult.created_at >= cutoff)

    if category:
        query = query.filter_by(category=category)

    if min_score > 0:
        query = query.filter(TenderResult.score >= min_score)

    if search:
        query = query.filter(
            db.or_(
                TenderResult.title.ilike(f"%{search}%"),
                TenderResult.description.ilike(f"%{search}%"),
                TenderResult.buyer.ilike(f"%{search}%"),
            )
        )
    return query


def _filtered_tenders_from_request(base_query, settings: AppSettings):
    sort_by = request.args.get("sort", "recommended")
    category = request.args.get("category", "")
    min_score = request.args.get("min_score", "0")
    search = request.args.get("search", "").strip()
    recent_days = _parse_recent_days(request.args.get("recent_days", "30"))
    shortlist_mode = request.args.get("shortlist_mode", _shortlist_default_mode(settings)).strip().lower()
    if shortlist_mode not in SHORTLIST_MODES:
        shortlist_mode = _shortlist_default_mode(settings)

    geographic_scope = request.args.get("geographic_scope", "").strip()
    africa_priority_flag = request.args.get("africa_priority_flag", "").strip()
    donor_flag = request.args.get("donor_or_multilateral_flag", "").strip()
    implementation_region = request.args.get("implementation_region", "").strip()
    buyer_region = request.args.get("buyer_region", "").strip()
    recommendation_filter = request.args.get("recommendation", "shortlist").strip().upper()
    queue_bucket = request.args.get("queue_bucket", "").strip()

    try:
        min_score = float(min_score)
    except (ValueError, TypeError):
        min_score = 0.0

    query = _apply_scan_filters(base_query, recent_days, category, min_score, search)

    if geographic_scope:
        query = query.filter(TenderResult.geographic_scope == geographic_scope)

    if africa_priority_flag in {"true", "false"}:
        query = query.filter(TenderResult.africa_priority_flag == (africa_priority_flag == "true"))

    if donor_flag in {"true", "false"}:
        query = query.filter(TenderResult.donor_or_multilateral_flag == (donor_flag == "true"))

    if implementation_region:
        query = query.filter(TenderResult.implementation_region == implementation_region)

    if buyer_region:
        query = query.filter(TenderResult.buyer_region == buyer_region)

    if queue_bucket:
        query = query.filter(TenderResult.queue_bucket == queue_bucket)

    if recommendation_filter == "SHORTLIST":
        query = query.filter(TenderResult.recommendation.in_(["GO", "REVIEW"]))
    elif recommendation_filter in {"GO", "REVIEW", "NO-GO"}:
        query = query.filter(TenderResult.recommendation == recommendation_filter)

    if settings.africa_only_mode:
        query = query.filter(TenderResult.africa_priority_flag.is_(True))
        shortlist_mode = "africa"

    results = query.all()
    results = [t for t in results if shortlist_mode_match(t, shortlist_mode)]

    if sort_by == "fit_score":
        results = sorted(results, key=lambda x: x.score or 0, reverse=True)
    elif sort_by == "deadline":
        results = sorted(results, key=lambda x: x.deadline or "9999-12-31")
    elif sort_by == "newest":
        results = sorted(results, key=lambda x: x.created_at or datetime.min, reverse=True)
    elif sort_by == "ranking":
        results = sorted(results, key=lambda x: x.ranking_score or 0, reverse=True)
    else:
        results = sorted(results, key=tender_sort_key)

    return {
        "results": results,
        "sort_by": sort_by,
        "category": category,
        "min_score": min_score,
        "search": search,
        "recent_days": recent_days,
        "shortlist_mode": shortlist_mode,
        "geographic_scope": geographic_scope,
        "africa_priority_flag": africa_priority_flag,
        "donor_or_multilateral_flag": donor_flag,
        "implementation_region": implementation_region,
        "buyer_region": buyer_region,
        "recommendation_filter": recommendation_filter,
        "queue_bucket": queue_bucket,
    }


def _parse_recent_days(value: str) -> int:
    try:
        days = int(value)
    except (TypeError, ValueError):
        return 30
    return days if days in RECENT_WINDOW_OPTIONS else 30


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
            "favorite": source.favorite,
            "source_group": source.source_group,
        })
    
    return jsonify(status)


@main.route("/")
def dashboard():
    """Dashboard with statistics and overview"""
    one_month_ago = datetime.utcnow() - timedelta(days=30)
    live_query = TenderResult.query.filter(
        TenderResult.created_at >= one_month_ago,
        TenderResult.recommendation.in_(["GO", "REVIEW"]),
    )

    total_tenders = live_query.count()
    high_score_count = live_query.filter(TenderResult.score >= 70).count()
    saved_count = TenderResult.query.filter_by(saved=True).filter(TenderResult.created_at >= one_month_ago).count()
    favorite_count = TenderResult.query.filter_by(favorite=True).filter(TenderResult.created_at >= one_month_ago).count()
    active_sources = TenderSource.query.filter_by(active=True).count()

    africa_live = live_query.filter(TenderResult.africa_priority_flag.is_(True)).count()
    global_live = live_query.filter(TenderResult.africa_priority_flag.is_(False)).count()
    africa_go = live_query.filter(
        TenderResult.africa_priority_flag.is_(True),
        TenderResult.recommendation == "GO",
    ).count()
    africa_review = live_query.filter(
        TenderResult.africa_priority_flag.is_(True),
        TenderResult.recommendation == "REVIEW",
    ).count()
    global_go = live_query.filter(
        TenderResult.africa_priority_flag.is_(False),
        TenderResult.recommendation == "GO",
    ).count()
    global_review = live_query.filter(
        TenderResult.africa_priority_flag.is_(False),
        TenderResult.recommendation == "REVIEW",
    ).count()
    donor_africa_targeted = live_query.filter(
        TenderResult.donor_or_multilateral_flag.is_(True),
        TenderResult.africa_priority_flag.is_(True),
    ).count()

    source_contributions = db.session.query(
        TenderSource.name,
        db.func.count(TenderResult.id).label('count')
    ).outerjoin(TenderResult).group_by(TenderSource.name).all()

    categories = db.session.query(
        TenderResult.category,
        db.func.count(TenderResult.id).label('count')
    ).filter(TenderResult.created_at >= one_month_ago).group_by(TenderResult.category).all()

    recent_tenders = sorted(
        live_query.order_by(TenderResult.created_at.desc()).limit(20).all(),
        key=tender_sort_key,
    )[:10]

    top_african_countries = (
        db.session.query(
            TenderResult.country,
            db.func.count(TenderResult.id).label("count"),
        )
        .filter(
            TenderResult.created_at >= one_month_ago,
            TenderResult.africa_priority_flag.is_(True),
            TenderResult.recommendation.in_(["GO", "REVIEW"]),
        )
        .group_by(TenderResult.country)
        .order_by(db.desc("count"))
        .limit(5)
        .all()
    )
    top_global_source_types = (
        db.session.query(
            TenderResult.source_group,
            db.func.count(TenderResult.id).label("count"),
        )
        .filter(
            TenderResult.created_at >= one_month_ago,
            TenderResult.africa_priority_flag.is_(False),
            TenderResult.recommendation.in_(["GO", "REVIEW"]),
        )
        .group_by(TenderResult.source_group)
        .order_by(db.desc("count"))
        .limit(5)
        .all()
    )
    source_mix = (
        db.session.query(
            TenderSource.source_group,
            db.func.count(TenderSource.id).label("count"),
        )
        .filter(TenderSource.active.is_(True))
        .group_by(TenderSource.source_group)
        .order_by(db.desc("count"))
        .all()
    )

    return render_template(
        "dashboard.html",
        total_tenders=total_tenders,
        high_score_count=high_score_count,
        saved_count=saved_count,
        favorite_count=favorite_count,
        active_sources=active_sources,
        africa_live=africa_live,
        global_live=global_live,
        africa_go=africa_go,
        africa_review=africa_review,
        global_go=global_go,
        global_review=global_review,
        donor_africa_targeted=donor_africa_targeted,
        source_contributions=source_contributions,
        categories=categories,
        recent_tenders=recent_tenders,
        top_african_countries=top_african_countries,
        top_global_source_types=top_global_source_types,
        source_mix=source_mix,
    )


@main.route("/scan", methods=["GET", "POST"])
def scan():
    settings = _get_settings()
    if request.method == "POST":
        from app.notifications import notify_new_tenders

        run_scan()
        unnotified = TenderResult.query.filter_by(notified=False).all()
        if unnotified:
            notify_new_tenders(unnotified)
            for tender in unnotified:
                tender.notified = True
            db.session.commit()
        return redirect(url_for("main.scan", shortlist_mode=_shortlist_default_mode(settings)))

    filter_state = _filtered_tenders_from_request(TenderResult.query, settings)

    categories = db.session.query(TenderResult.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    geographic_scopes = [row[0] for row in db.session.query(TenderResult.geographic_scope).distinct().all() if row[0]]
    implementation_regions = [row[0] for row in db.session.query(TenderResult.implementation_region).distinct().all() if row[0]]
    buyer_regions = [row[0] for row in db.session.query(TenderResult.buyer_region).distinct().all() if row[0]]
    secondary_review_count = TenderResult.query.filter(
        TenderResult.queue_bucket == "secondary_review",
        TenderResult.created_at >= datetime.utcnow() - timedelta(days=filter_state["recent_days"]),
    ).count()

    return render_template(
        "scan_results.html",
        results=filter_state["results"],
        sort_by=filter_state["sort_by"],
        category=filter_state["category"],
        min_score=filter_state["min_score"],
        search=filter_state["search"],
        recent_days=filter_state["recent_days"],
        recent_window_options=RECENT_WINDOW_OPTIONS,
        categories=categories,
        shortlist_mode=filter_state["shortlist_mode"],
        geographic_scope=filter_state["geographic_scope"],
        africa_priority_flag=filter_state["africa_priority_flag"],
        donor_or_multilateral_flag=filter_state["donor_or_multilateral_flag"],
        implementation_region=filter_state["implementation_region"],
        buyer_region=filter_state["buyer_region"],
        recommendation_filter=filter_state["recommendation_filter"],
        queue_bucket=filter_state["queue_bucket"],
        geographic_scopes=geographic_scopes,
        implementation_regions=implementation_regions,
        buyer_regions=buyer_regions,
        settings=settings,
        shortlist_modes=SHORTLIST_MODES,
        secondary_review_count=secondary_review_count,
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


@main.route("/source/<int:sid>/group", methods=["POST"])
def update_source_group(sid):
    """Update source group/tag for a source."""
    s = TenderSource.query.get_or_404(sid)
    group = (request.form.get("source_group", "experimental") or "experimental").strip()
    if group not in SOURCE_GROUP_OPTIONS:
        group = "experimental"
    s.source_group = group
    s.source_tags = json.dumps([group])
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
        source_group = (request.form.get("source_group", "experimental") or "experimental").strip()
        if source_group not in SOURCE_GROUP_OPTIONS:
            source_group = "experimental"
        
        if not name or not url:
            active_sources = TenderSource.query.filter_by(active=True).all()
            inactive_sources = TenderSource.query.filter_by(active=False).all()
            return render_template(
                "sources.html",
                active_sources=active_sources,
                inactive_sources=inactive_sources,
                error="Name and URL are required",
                source_group_options=SOURCE_GROUP_OPTIONS,
            ), 400
        
        # Check if source already exists
        if TenderSource.query.filter_by(url=url).first():
            active_sources = TenderSource.query.filter_by(active=True).all()
            inactive_sources = TenderSource.query.filter_by(active=False).all()
            return render_template(
                "sources.html",
                active_sources=active_sources,
                inactive_sources=inactive_sources,
                error="This source URL already exists",
                source_group_options=SOURCE_GROUP_OPTIONS,
            ), 400
        
        # Create new source
        new_source = TenderSource(
            name=name,
            url=url,
            active=True,
            source_group=source_group,
            source_tags=json.dumps([source_group]),
        )
        db.session.add(new_source)
        db.session.commit()
        
        return redirect(url_for("main.sources"))
    
    active_sources = TenderSource.query.filter_by(active=True).all()
    inactive_sources = TenderSource.query.filter_by(active=False).all()
    
    return render_template(
        "sources.html",
        active_sources=active_sources,
        inactive_sources=inactive_sources,
        source_group_options=SOURCE_GROUP_OPTIONS,
    )


@main.route("/discovery")
def discovery_dashboard():
    """
    Backward-compatible route kept for templates that still reference
    discovery dashboard navigation.
    """
    return redirect(url_for("main.settings"))


@main.route("/saved")
def saved():
    settings = _get_settings()
    results = (
        TenderResult.query
        .filter_by(saved=True)
        .all()
    )
    results = sorted(results, key=tender_sort_key)
    return render_template(
        "scan_results.html",
        results=results,
        title="Saved Tenders",
        sort_by="recommended",
        category="",
        min_score=0,
        search="",
        recent_days=30,
        recent_window_options=RECENT_WINDOW_OPTIONS,
        categories=[],
        shortlist_mode="combined",
        geographic_scope="",
        africa_priority_flag="",
        donor_or_multilateral_flag="",
        implementation_region="",
        buyer_region="",
        recommendation_filter="SHORTLIST",
        queue_bucket="",
        geographic_scopes=[],
        implementation_regions=[],
        buyer_regions=[],
        settings=settings,
        shortlist_modes=SHORTLIST_MODES,
        secondary_review_count=0,
    )


@main.route("/favorites")
def favorites():
    """View favorite tenders"""
    settings = _get_settings()
    results = (
        TenderResult.query
        .filter_by(favorite=True)
        .all()
    )
    results = sorted(results, key=tender_sort_key)
    return render_template(
        "scan_results.html",
        results=results,
        title="Favorite Tenders",
        sort_by="recommended",
        category="",
        min_score=0,
        search="",
        recent_days=30,
        recent_window_options=RECENT_WINDOW_OPTIONS,
        categories=[],
        shortlist_mode="combined",
        geographic_scope="",
        africa_priority_flag="",
        donor_or_multilateral_flag="",
        implementation_region="",
        buyer_region="",
        recommendation_filter="SHORTLIST",
        queue_bucket="",
        geographic_scopes=[],
        implementation_regions=[],
        buyer_regions=[],
        settings=settings,
        shortlist_modes=SHORTLIST_MODES,
        secondary_review_count=0,
    )


@main.route("/save/<int:rid>", methods=["POST"])
def save(rid):
    r = TenderResult.query.get_or_404(rid)
    r.saved = True
    db.session.commit()
    
    # Update golden embeddings for ML learning
    try:
        from app.ml_ranker import update_golden_embeddings
        update_golden_embeddings()
    except Exception as e:
        pass  # Non-critical, don't break the save
    
    return redirect(request.referrer or url_for("main.scan"))


@main.route("/toggle-save/<int:rid>", methods=["POST"])
def toggle_save(rid):
    """Backward-compatible save toggle endpoint used by older templates."""
    r = TenderResult.query.get_or_404(rid)
    r.saved = not bool(r.saved)
    db.session.commit()

    if r.saved:
        try:
            from app.ml_ranker import update_golden_embeddings
            update_golden_embeddings()
        except Exception:
            pass

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
    
    # Update golden embeddings for ML learning
    if r.favorite:
        try:
            from app.ml_ranker import update_golden_embeddings
            update_golden_embeddings()
        except Exception as e:
            pass  # Non-critical
    
    return redirect(request.referrer or url_for("main.scan"))


@main.route("/settings", methods=["GET", "POST"])
def settings():
    """View and update app settings"""
    settings = _get_settings()
    
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

        settings.africa_priority_weight = float(request.form.get("africa_priority_weight", 12.0))
        settings.global_relevance_threshold = float(request.form.get("global_relevance_threshold", 28.0))
        settings.donor_multilateral_boost = float(request.form.get("donor_multilateral_boost", 8.0))
        settings.africa_only_mode = request.form.get("africa_only_mode") == "on"
        settings.include_global_sources = request.form.get("include_global_sources") == "on"
        settings.include_global_in_default_shortlist = request.form.get("include_global_in_default_shortlist") == "on"
        settings.secondary_review_queue_threshold = float(request.form.get("secondary_review_queue_threshold", 16.0))
        
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


@main.route("/api/ml/status")
def ml_status():
    """Get ML model status"""
    try:
        from app.ml_ranker import get_model_status
        status = get_model_status()
        return jsonify({"success": True, **status})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@main.route("/api/ml/train", methods=["POST"])
def ml_train():
    """Train ML ranker model from user feedback"""
    try:
        from app.ml_ranker import train_ranker_model, update_golden_embeddings
        
        # First update golden embeddings
        update_golden_embeddings()
        
        # Then train the ranker
        success, message = train_ranker_model()
        
        return jsonify({"success": success, "message": message})
    except ImportError as e:
        return jsonify({
            "success": False, 
            "message": f"ML dependencies not installed: {e}. Run: pip install lightgbm sentence-transformers"
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@main.route("/api/ml/score/<int:rid>")
def ml_score_tender(rid):
    """Get ML score breakdown for a specific tender"""
    try:
        from app.ml_ranker import ml_score
        
        tender = TenderResult.query.get_or_404(rid)
        result = ml_score(tender.title, tender.title)
        
        return jsonify({"success": True, "tender_id": rid, **result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@main.route("/export/csv")
def export_csv():
    """Export tenders to CSV file"""
    settings = _get_settings()
    filter_state = _filtered_tenders_from_request(TenderResult.query, settings)
    results = filter_state["results"]

    si = StringIO()
    writer = csv.writer(si)

    writer.writerow([
        "Title",
        "Recommendation",
        "Fit Score",
        "Ranking Score",
        "Geographic Scope",
        "Africa Priority",
        "Donor/Multilateral",
        "Region",
        "Country",
        "Buyer Region",
        "Implementation Region",
        "Source Group",
        "Queue Bucket",
        "Category",
        "Buyer",
        "Deadline",
        "Link",
        "Keywords Matched",
        "Saved",
        "Favorite",
        "Date Added",
    ])

    for tender in results:
        writer.writerow([
            tender.title or "",
            tender.recommendation or "",
            f"{tender.score:.1f}" if tender.score else "0",
            f"{tender.ranking_score:.1f}" if tender.ranking_score else "0",
            tender.geographic_scope or "",
            "Yes" if tender.africa_priority_flag else "No",
            "Yes" if tender.donor_or_multilateral_flag else "No",
            tender.region or "",
            tender.country or "",
            tender.buyer_region or "",
            tender.implementation_region or "",
            tender.source_group or "",
            tender.queue_bucket or "",
            tender.category or "",
            tender.buyer or "",
            tender.deadline or "",
            tender.link or "",
            tender.keywords_matched or "",
            "Yes" if tender.saved else "No",
            "Yes" if tender.favorite else "No",
            tender.created_at.strftime("%Y-%m-%d %H:%M") if tender.created_at else "",
        ])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=tenderwatch_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    output.headers["Content-type"] = "text/csv"
    
    return output


from app.translator import translate_to_english, detect_language

# ...existing code...

# Ensure auto-translation in tender detail view
## Duplicate tender_detail removed; see earlier definition for logic.

# Ensure auto-translation in scan results view
## Duplicate scan removed; see earlier definition for logic.
