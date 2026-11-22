"""Notification list and read-state actions."""

from flask import redirect, render_template, request, url_for
from flask_login import current_user

from app.constants import ROLES
from app.notifications import bp
from app.services import notifications as service
from app.utils.decorators import role_required
from app.utils.request_args import page_arg
from app.utils.security import is_safe_redirect_target


def _back():
    target = request.form.get("next")
    if is_safe_redirect_target(target):
        return redirect(target)
    return redirect(url_for("notifications.index"))


@bp.route("/")
@role_required(*ROLES)
def index():
    pagination = service.list_notifications(current_user.id, page_arg())
    return render_template(
        "notifications/index.html",
        pagination=pagination,
        destination=service.destination_url,
    )


@bp.route("/<int:notification_id>/read", methods=["POST"])
@role_required(*ROLES)
def mark_read(notification_id):
    service.mark_read(current_user.id, notification_id)
    return _back()


@bp.route("/read-all", methods=["POST"])
@role_required(*ROLES)
def mark_all_read():
    service.mark_all_read(current_user.id)
    return _back()
