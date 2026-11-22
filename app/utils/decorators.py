"""Authorization decorators. Every protected view re-checks role server-side."""

from functools import wraps

from flask import abort
from flask_login import current_user

from app.extensions import login_manager


def role_required(*roles):
    """Require an authenticated, active user holding one of ``roles``."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            if not current_user.is_active or current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator
