from flask import Blueprint, abort
from flask_login import current_user

from app.constants import ROLE_ADMIN

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
def require_admin():
    """Defence in depth: every admin endpoint is admin-only, even new ones."""
    if not current_user.is_authenticated:
        from app.extensions import login_manager

        return login_manager.unauthorized()
    if current_user.role != ROLE_ADMIN:
        abort(403)


from app.admin import routes  # noqa: E402,F401
