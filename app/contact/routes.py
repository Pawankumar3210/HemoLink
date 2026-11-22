"""Contact-request workflow: request, accept/decline, withdraw, revoke."""

from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.constants import ROLE_DONOR, ROLE_RECIPIENT
from app.contact import bp
from app.services import blood_requests, contacts, donors
from app.services.errors import ServiceError
from app.services.validation import validate_contact_message
from app.utils.decorators import role_required
from app.utils.ratelimit import rate_limit
from app.utils.request_args import page_arg


def _page_size():
    return current_app.config["TABLE_PAGE_SIZE"]


@bp.route("/request/<int:profile_id>", methods=["GET", "POST"])
@role_required(ROLE_RECIPIENT)
@rate_limit("contact-create", 10, 3600, key="user")
def request_form(profile_id):
    profile = donors.get_public_profile(profile_id)
    if profile is None:
        abort(404)
    errors = {}
    if request.method == "POST":
        cleaned, errors = validate_contact_message(request.form)
        if not errors:
            try:
                contact = contacts.create_contact_request(
                    current_user, profile_id, cleaned
                )
            except ServiceError as error:
                if error.status == 404:
                    abort(404)
                errors[error.field or "form"] = error.message
            else:
                flash("Your contact request has been sent to the donor.", "success")
                return redirect(url_for("contact.detail", contact_id=contact.id))
    return (
        render_template(
            "contact/request_form.html",
            profile=profile,
            form=request.form,
            errors=errors,
            my_requests=blood_requests.open_requests_for_user(current_user),
        ),
        400 if errors else 200,
    )


@bp.route("/incoming")
@role_required(ROLE_DONOR)
def incoming():
    pagination = contacts.incoming_for_donor(current_user, page_arg(), _page_size())
    return render_template("contact/incoming.html", pagination=pagination)


@bp.route("/history")
@role_required(ROLE_DONOR)
def history():
    pagination = contacts.history_for_donor(current_user, page_arg(), _page_size())
    return render_template("contact/history.html", pagination=pagination)


@bp.route("/tracking")
@role_required(ROLE_RECIPIENT)
def tracking():
    pagination = contacts.list_for_recipient(current_user, page_arg(), _page_size())
    return render_template("contact/tracking.html", pagination=pagination)


@bp.route("/<int:contact_id>")
@role_required(ROLE_DONOR, ROLE_RECIPIENT)
def detail(contact_id):
    contact = contacts.get_for_party(contact_id, current_user)
    if contact is None:
        abort(404)
    as_donor = contact.donor_id == current_user.id
    return render_template("contact/detail.html", contact=contact, as_donor=as_donor)


def _act(action, contact_id, success):
    try:
        action(contact_id, current_user)
    except ServiceError as error:
        if error.status == 404:
            abort(404)
        flash(error.message, "error")
    else:
        flash(success, "success")
    return redirect(url_for("contact.detail", contact_id=contact_id))


@bp.route("/<int:contact_id>/accept", methods=["POST"])
@role_required(ROLE_DONOR)
def accept(contact_id):
    return _act(
        lambda cid, user: contacts.respond(cid, user, True),
        contact_id,
        "You accepted this request. The recipient can now see your phone number.",
    )


@bp.route("/<int:contact_id>/decline", methods=["POST"])
@role_required(ROLE_DONOR)
def decline(contact_id):
    return _act(
        lambda cid, user: contacts.respond(cid, user, False),
        contact_id,
        "You declined this request. Your contact details stay private.",
    )


@bp.route("/<int:contact_id>/revoke", methods=["POST"])
@role_required(ROLE_DONOR)
def revoke(contact_id):
    return _act(
        contacts.revoke_access,
        contact_id,
        "Access ended. The recipient can no longer see your phone number.",
    )


@bp.route("/<int:contact_id>/withdraw", methods=["POST"])
@role_required(ROLE_RECIPIENT)
def withdraw(contact_id):
    return _act(contacts.withdraw, contact_id, "Your contact request was withdrawn.")
