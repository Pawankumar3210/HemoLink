"""Role dashboards and account settings."""

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, logout_user

from app.constants import ROLE_ADMIN, ROLE_DONOR, ROLE_RECIPIENT, ROLES
from app.dashboard import bp
from app.services import blood_requests, contacts, stats, users
from app.services.errors import ServiceError
from app.services.notifications import recent_notifications
from app.services.validation import validate_account_update, validate_password_change
from app.utils.decorators import role_required
from app.utils.ratelimit import rate_limit


@bp.route("/dashboard")
@login_required
def home():
    """Send each role to its own dashboard."""
    if current_user.role == ROLE_ADMIN:
        return redirect(url_for("admin.index"))
    if current_user.role == ROLE_DONOR:
        return redirect(url_for("dashboard.donor"))
    return redirect(url_for("dashboard.recipient"))


@bp.route("/dashboard/donor")
@role_required(ROLE_DONOR)
def donor():
    pending = contacts.incoming_for_donor(current_user, 1, per_page=3)
    return render_template(
        "dashboard/donor.html",
        profile=current_user.donor_profile,
        stats=stats.donor_dashboard_stats(current_user),
        pending=pending.items,
        notifications=recent_notifications(current_user.id),
    )


@bp.route("/dashboard/recipient")
@role_required(ROLE_RECIPIENT)
def recipient():
    return render_template(
        "dashboard/recipient.html",
        stats=stats.recipient_dashboard_stats(current_user),
        open_requests=blood_requests.open_requests_for_user(current_user)[:4],
        contact_requests=contacts.list_for_recipient(current_user, 1, per_page=4).items,
        notifications=recent_notifications(current_user.id),
    )


def _account_page(active=None, errors=None, form=None, status=200):
    return (
        render_template(
            "dashboard/account.html",
            active=active,
            errors=errors or {},
            form=form if form is not None else {},
        ),
        status,
    )


@bp.route("/account")
@role_required(*ROLES)
def account():
    return _account_page()


@bp.route("/account/profile", methods=["POST"])
@role_required(*ROLES)
def update_account():
    cleaned, errors = validate_account_update(request.form)
    if errors:
        return _account_page("profile", errors, request.form, 400)
    users.update_account(current_user, cleaned)
    flash("Your details have been updated.", "success")
    return redirect(url_for("dashboard.account"))


@bp.route("/account/password", methods=["POST"])
@role_required(*ROLES)
@rate_limit("change-password", 10, 900, key="user")
def change_password():
    cleaned, errors = validate_password_change(request.form, current_user.email)
    if not errors:
        try:
            users.change_password(
                current_user, cleaned["current_password"], cleaned["new_password"]
            )
        except ServiceError as error:
            errors[error.field or "form"] = error.message
    if errors:
        return _account_page("password", errors, request.form, 400)
    flash("Your password has been changed.", "success")
    return redirect(url_for("dashboard.account"))


@bp.route("/account/delete", methods=["POST"])
@role_required(*ROLES)
@rate_limit("delete-account", 5, 900, key="user")
def delete_account():
    password = request.form.get("password") or ""
    confirmed = request.form.get("confirm_delete") == "on"
    errors = {}
    if not confirmed:
        errors["confirm_delete"] = "Tick the box to confirm the deletion."
    if not password:
        errors["password"] = "Enter your password to confirm."
    if not errors:
        try:
            users.delete_account(current_user, password)
        except ServiceError as error:
            errors[error.field or "form"] = error.message
    if errors:
        return _account_page("delete", errors, request.form, 400)
    logout_user()
    flash("Your account has been deleted and your personal details removed.", "success")
    return redirect(url_for("main.index"))
