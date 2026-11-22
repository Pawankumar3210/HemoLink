"""Public pages and health checks."""

from flask import current_app, jsonify, render_template
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.main import bp
from app.services.stats import landing_stats


@bp.route("/")
def index():
    try:
        stats = landing_stats()
    except SQLAlchemyError:
        db.session.rollback()
        stats = None
    return render_template("main/index.html", stats=stats)


@bp.route("/about")
def about():
    return render_template("main/about.html")


@bp.route("/how-it-works")
def how_it_works():
    return render_template("main/how_it_works.html")


@bp.route("/sdg-3")
def sdg3():
    return render_template("main/sdg3.html")


@bp.route("/privacy")
def privacy():
    return render_template("main/privacy.html")


@bp.route("/terms")
def terms():
    return render_template("main/terms.html")


@bp.route("/health/live")
def health_live():
    """Liveness: the process is running and can answer HTTP."""
    release = current_app.config.get("RELEASE")
    if release:
        return jsonify(status="ok", release=release)
    return jsonify(status="ok")


@bp.route("/health/ready")
def health_ready():
    """Readiness: the database accepts queries. Reveals no internals on failure."""
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - any failure means "not ready"
        db.session.rollback()
        current_app.logger.error("readiness check failed: database unreachable")
        return jsonify(status="unavailable"), 503
    return jsonify(status="ready")
