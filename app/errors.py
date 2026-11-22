"""Friendly error pages and safe production error handling."""

from flask import render_template, request
from flask_wtf.csrf import CSRFError
from sqlalchemy.exc import OperationalError
from werkzeug.exceptions import TooManyRequests

from app.extensions import db

FALLBACK_PAGE = (
    "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
    "<title>HemoLink</title></head><body><h1>Something went wrong</h1>"
    "<p>Please try again in a moment.</p></body></html>"
)


def _render(template, status, **context):
    """Render an error page; never let rendering itself raise another error."""
    try:
        return render_template(template, **context), status
    except Exception:  # noqa: BLE001 - last-resort fallback
        return FALLBACK_PAGE, status


def register_error_handlers(app):
    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return _render("errors/400.html", 400, message=error.description)

    @app.errorhandler(400)
    def bad_request(error):
        return _render("errors/400.html", 400, message=None)

    @app.errorhandler(403)
    def forbidden(error):
        return _render("errors/403.html", 403)

    @app.errorhandler(404)
    def not_found(error):
        return _render("errors/404.html", 404)

    @app.errorhandler(TooManyRequests)
    def too_many_requests(error):
        body, status = _render(
            "errors/429.html", 429, retry_after=getattr(error, "retry_after", None)
        )
        response = app.make_response((body, status))
        if getattr(error, "retry_after", None):
            response.headers["Retry-After"] = str(error.retry_after)
        return response

    @app.errorhandler(OperationalError)
    def database_unavailable(error):
        db.session.rollback()
        app.logger.error("database error on %s %s", request.method, request.path)
        return _render("errors/503.html", 503)

    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        return _render("errors/500.html", 500)
