"""Administrator dashboard and moderation tools."""

from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.admin import bp
from app.constants import (
    ACCOUNT_ACTIVE,
    ACCOUNT_STATUSES,
    ACCOUNT_SUSPENDED,
    AVAILABILITY_STATUSES,
    BLOOD_GROUPS,
    CONTACT_STATUSES,
    REQUEST_REJECTED,
    REQUEST_STATUSES,
    ROLE_ADMIN,
    ROLES,
)
from app.extensions import db
from app.models import BloodRequest, User
from app.services import admin as service
from app.services import blood_requests, stats
from app.services.errors import ServiceError
from app.services.validation import clean_text, validate_notice, validate_reason
from app.utils.decorators import role_required
from app.utils.request_args import choice_arg, page_arg
from app.utils.security import is_safe_redirect_target


def _size():
    return current_app.config["TABLE_PAGE_SIZE"]


def _text_arg(name, limit=100):
    return clean_text(request.args.get(name), limit)


@bp.route("/")
@role_required(ROLE_ADMIN)
def index():
    return render_template(
        "admin/index.html", stats=stats.platform_stats(), recent=service.recent_audit()
    )


@bp.route("/users")
@role_required(ROLE_ADMIN)
def users():
    filters = {
        "q": _text_arg("q"),
        "role": choice_arg("role", ROLES),
        "status": choice_arg("status", ACCOUNT_STATUSES),
    }
    pagination = service.list_users(filters, page_arg(), _size())
    return render_template("admin/users.html", pagination=pagination, filters=filters)


@bp.route("/users/<int:user_id>")
@role_required(ROLE_ADMIN)
def user_detail(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    return render_template("admin/user_detail.html", user=user)


def _set_status(user_id, new_status, success):
    try:
        service.set_account_status(current_user, user_id, new_status)
    except ServiceError as error:
        if error.status == 404:
            abort(404)
        flash(error.message, "error")
    else:
        flash(success, "success")
    return redirect(url_for("admin.user_detail", user_id=user_id))


@bp.route("/users/<int:user_id>/suspend", methods=["POST"])
@role_required(ROLE_ADMIN)
def suspend_user(user_id):
    return _set_status(user_id, ACCOUNT_SUSPENDED, "The account has been suspended.")


@bp.route("/users/<int:user_id>/reactivate", methods=["POST"])
@role_required(ROLE_ADMIN)
def reactivate_user(user_id):
    return _set_status(user_id, ACCOUNT_ACTIVE, "The account has been reactivated.")


@bp.route("/donors")
@role_required(ROLE_ADMIN)
def donors():
    filters = {
        "q": _text_arg("q"),
        "blood_group": choice_arg("blood_group", BLOOD_GROUPS),
        "availability": choice_arg("availability", AVAILABILITY_STATUSES),
        "state": _text_arg("state"),
        "city": _text_arg("city", 80),
    }
    pagination = service.list_donors(filters, page_arg(), _size())
    return render_template("admin/donors.html", pagination=pagination, filters=filters)


@bp.route("/requests")
@role_required(ROLE_ADMIN)
def requests():
    filters = {
        "status": choice_arg("status", REQUEST_STATUSES),
        "blood_group": choice_arg("blood_group", BLOOD_GROUPS),
        "state": _text_arg("state"),
        "city": _text_arg("city", 80),
    }
    pagination = service.list_requests(filters, page_arg(), _size())
    return render_template(
        "admin/requests.html", pagination=pagination, filters=filters
    )


@bp.route("/requests/<int:request_id>/status", methods=["POST"])
@role_required(ROLE_ADMIN)
def request_status(request_id):
    blood_request = db.session.get(BloodRequest, request_id)
    if blood_request is None:
        abort(404)
    new_status = (request.form.get("status") or "").strip()
    if new_status not in REQUEST_STATUSES:
        flash("Choose a valid status.", "error")
        return redirect(url_for("admin.requests"))
    note = None
    if new_status == REQUEST_REJECTED:
        cleaned, errors = validate_reason(request.form)
        if errors:
            flash("Enter a short reason for rejecting this request.", "error")
            return redirect(url_for("admin.requests"))
        note = cleaned["reason"]
    try:
        blood_requests.change_status(blood_request, new_status, current_user, note)
    except ServiceError as error:
        flash(error.message, "error")
    else:
        flash("The request status has been updated.", "success")
    target = request.form.get("next")
    if is_safe_redirect_target(target):
        return redirect(target)
    return redirect(url_for("admin.requests"))


@bp.route("/contacts")
@role_required(ROLE_ADMIN)
def contacts():
    filters = {"status": choice_arg("status", CONTACT_STATUSES)}
    pagination = service.list_contacts(filters, page_arg(), _size())
    return render_template(
        "admin/contacts.html", pagination=pagination, filters=filters
    )


@bp.route("/audit")
@role_required(ROLE_ADMIN)
def audit():
    filters = {"action": _text_arg("action", 40)}
    pagination = service.list_audit(filters, page_arg(), _size())
    return render_template("admin/audit.html", pagination=pagination, filters=filters)


@bp.route("/notices", methods=["GET", "POST"])
@role_required(ROLE_ADMIN)
def notices():
    errors = {}
    if request.method == "POST":
        cleaned, errors = validate_notice(request.form)
        if not errors:
            sent = service.broadcast_notice(current_user, cleaned)
            flash("Notice sent to %d users." % sent, "success")
            return redirect(url_for("admin.notices"))
    return (
        render_template("admin/notices.html", form=request.form, errors=errors),
        400 if errors else 200,
    )


@bp.route("/system")
@role_required(ROLE_ADMIN)
def system():
    return render_template("admin/system.html", info=service.system_info())
