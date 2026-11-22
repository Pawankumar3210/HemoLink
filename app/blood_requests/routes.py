"""Recipient blood requests, plus read-only views for donors and admins."""

from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import select

from app.blood_requests import bp
from app.constants import (
    REQUEST_CANCELLED,
    REQUEST_FULFILLED,
    REQUEST_STATUSES,
    ROLE_ADMIN,
    ROLE_DONOR,
    ROLE_RECIPIENT,
)
from app.extensions import db
from app.models import BloodRequest, ContactRequest
from app.services import blood_requests
from app.services.errors import ServiceError
from app.services.validation import validate_blood_request
from app.utils.decorators import role_required
from app.utils.ratelimit import rate_limit
from app.utils.request_args import choice_arg, page_arg


def _owned_or_404(request_id):
    """Fetch a request only if the signed-in recipient owns it."""
    blood_request = db.session.get(BloodRequest, request_id)
    if blood_request is None or blood_request.requester_id != current_user.id:
        abort(404)
    return blood_request


def _form_from(blood_request):
    return {
        "blood_group": blood_request.blood_group,
        "units_required": blood_request.units_required,
        "hospital_name": blood_request.hospital_name or "",
        "state": blood_request.state,
        "city": blood_request.city,
        "required_by": blood_request.required_by.isoformat(),
        "urgency": blood_request.urgency,
        "notes": blood_request.notes or "",
    }


@bp.route("/")
@role_required(ROLE_RECIPIENT)
def index():
    status = choice_arg("status", REQUEST_STATUSES)
    pagination = blood_requests.list_for_requester(
        current_user, status, page_arg(), current_app.config["TABLE_PAGE_SIZE"]
    )
    return render_template("requests/list.html", pagination=pagination, status=status)


@bp.route("/new", methods=["GET", "POST"])
@role_required(ROLE_RECIPIENT)
@rate_limit("create-request", 20, 3600, key="user")
def create():
    errors = {}
    if request.method == "POST":
        cleaned, errors = validate_blood_request(request.form)
        if not errors:
            created = blood_requests.create_request(current_user, cleaned)
            flash("Your blood request has been posted.", "success")
            return redirect(url_for("blood_requests.detail", request_id=created.id))
    status = 400 if errors else 200
    return (
        render_template(
            "requests/form.html", form=request.form, errors=errors, editing=None
        ),
        status,
    )


@bp.route("/<int:request_id>")
@role_required(ROLE_RECIPIENT, ROLE_DONOR, ROLE_ADMIN)
def detail(request_id):
    blood_request = db.session.get(BloodRequest, request_id)
    if blood_request is None:
        abort(404)
    if not blood_requests.can_view(blood_request, current_user):
        abort(404)
    is_owner = blood_request.requester_id == current_user.id
    activity = []
    if is_owner:
        activity = list(
            db.session.scalars(
                select(ContactRequest)
                .where(
                    ContactRequest.blood_request_id == blood_request.id,
                    ContactRequest.recipient_id == current_user.id,
                )
                .order_by(ContactRequest.created_at.desc())
            )
        )
    return render_template(
        "requests/detail.html",
        blood_request=blood_request,
        is_owner=is_owner,
        activity=activity,
    )


@bp.route("/<int:request_id>/edit", methods=["GET", "POST"])
@role_required(ROLE_RECIPIENT)
def edit(request_id):
    blood_request = _owned_or_404(request_id)
    if not blood_request.is_open:
        flash("Only open requests can be edited.", "error")
        return redirect(url_for("blood_requests.detail", request_id=request_id))
    errors = {}
    if request.method == "POST":
        cleaned, errors = validate_blood_request(request.form)
        if not errors:
            try:
                blood_requests.update_request(blood_request, cleaned)
            except ServiceError as error:
                flash(error.message, "error")
            else:
                flash("Your request has been updated.", "success")
            return redirect(url_for("blood_requests.detail", request_id=request_id))
        form = request.form
    else:
        form = _form_from(blood_request)
    return (
        render_template(
            "requests/form.html", form=form, errors=errors, editing=blood_request
        ),
        400 if errors else 200,
    )


def _change(request_id, new_status, success):
    blood_request = _owned_or_404(request_id)
    try:
        blood_requests.change_status(blood_request, new_status, current_user)
    except ServiceError as error:
        flash(error.message, "error")
    else:
        flash(success, "success")
    return redirect(url_for("blood_requests.detail", request_id=request_id))


@bp.route("/<int:request_id>/cancel", methods=["POST"])
@role_required(ROLE_RECIPIENT)
def cancel(request_id):
    return _change(request_id, REQUEST_CANCELLED, "Your request has been cancelled.")


@bp.route("/<int:request_id>/fulfill", methods=["POST"])
@role_required(ROLE_RECIPIENT)
def fulfill(request_id):
    return _change(request_id, REQUEST_FULFILLED, "Marked as fulfilled. Thank you!")
