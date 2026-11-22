from flask import Blueprint

bp = Blueprint("blood_requests", __name__, url_prefix="/requests")

from app.blood_requests import routes  # noqa: E402,F401
