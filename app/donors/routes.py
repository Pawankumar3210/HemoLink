"""Donor self-service pages and recipient-facing donor search."""

from flask import (
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user

from app.constants import (
    AVAILABILITY_STATUSES,
    BLOOD_GROUPS,
    INDIAN_STATES,
    ROLE_DONOR,
    ROLE_RECIPIENT,
)
from app.donors import bp
from app.services import blood_requests, contacts, donors
from app.services.errors import ServiceError
from app.services.validation import (
    is_checked,
    validate_donor_fields,
    validate_search_filters,
)
from app.utils.decorators import role_required
from app.utils.request_args import choice_arg, page_arg


def _profile_form(profile):
    """Pre-fill the edit form from the stored profile."""
    if profile is None:
        return {"availability_status": "available"}
    return {
        "blood_group": profile.blood_group,
        "age": profile.age,
        "gender": profile.gender or "",
        "state": profile.state,
        "city": profile.city,
        "last_donation_date": (
            profile.last_donation_date.isoformat() if profile.last_donation_date else ""
        ),
        "availability_status": profile.availability_status,
        "visible_in_search": "on" if profile.visible_in_search else "",
        "share_last_donation_date": "on" if profile.share_last_donation_date else "",
    }


@bp.route("/donor/profile")
@role_required(ROLE_DONOR)
def profile():
    return render_template("donors/profile.html", profile=current_user.donor_profile)


@bp.route("/donor/profile/edit", methods=["GET", "POST"])
@role_required(ROLE_DONOR)
def edit_profile():
    errors = {}
    if request.method == "POST":
        cleaned, errors = validate_donor_fields(request.form)
        if not errors:
            donors.update_profile(current_user, cleaned)
            flash("Your donor profile has been saved.", "success")
            return redirect(url_for("donors.profile"))
        form = request.form
        status = 400
    else:
        form = _profile_form(current_user.donor_profile)
        status = 200
    return render_template("donors/edit_profile.html", form=form, errors=errors), status


@bp.route("/donor/availability", methods=["GET", "POST"])
@role_required(ROLE_DONOR)
def availability():
    profile = current_user.donor_profile
    errors = {}
    if request.method == "POST":
        status = (request.form.get("availability_status") or "").strip()
        if status not in AVAILABILITY_STATUSES:
            errors["availability_status"] = "Select an availability option."
        else:
            try:
                donors.set_availability(
                    current_user, status, is_checked(request.form, "visible_in_search")
                )
            except ServiceError as error:
                errors["form"] = error.message
            else:
                flash("Your availability settings have been saved.", "success")
                return redirect(url_for("donors.availability"))
        return (
            render_template(
                "donors/availability.html",
                profile=profile,
                form=request.form,
                errors=errors,
            ),
            400,
        )
    return render_template("donors/availability.html", profile=profile, errors=errors)


@bp.route("/donor/availability/quick", methods=["POST"])
@role_required(ROLE_DONOR)
def quick_availability():
    status = (request.form.get("availability_status") or "").strip()
    if status not in AVAILABILITY_STATUSES:
        flash("Select an availability option.", "error")
    else:
        try:
            donors.set_availability(current_user, status)
            flash("Availability updated.", "success")
        except ServiceError as error:
            flash(error.message, "error")
    return redirect(url_for("dashboard.donor"))


@bp.route("/donor/blood-requests")
@role_required(ROLE_DONOR)
def open_requests():
    profile = current_user.donor_profile
    # Default to the donor's own blood group and state; "all" (empty) widens it.
    blood_group = (
        choice_arg("blood_group", BLOOD_GROUPS)
        if "blood_group" in request.args
        else (profile.blood_group if profile else "")
    )
    state = (
        choice_arg("state", INDIAN_STATES)
        if "state" in request.args
        else (profile.state if profile else "")
    )
    pagination = blood_requests.open_requests_for_donors(
        {"blood_group": blood_group, "state": state},
        page_arg(),
        current_app.config["TABLE_PAGE_SIZE"],
    )
    return render_template(
        "donors/open_requests.html",
        pagination=pagination,
        filters={"blood_group": blood_group, "state": state},
    )


@bp.route("/donors/search")
def search():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
    if current_user.role == ROLE_DONOR:
        params = {}
        for key in ("blood_group", "state"):
            value = (request.args.get(key) or "").strip()
            if value:
                params[key] = value
        return redirect(url_for("donors.open_requests", **params))
    if current_user.role != ROLE_RECIPIENT:
        abort(403)
    filters, errors = validate_search_filters(request.args)
    pagination = donors.search_donors(
        filters, page_arg(), current_app.config["SEARCH_PAGE_SIZE"]
    )
    has_filters = any(
        filters[key] for key in ("blood_group", "state", "city", "availability", "q")
    )
    return (
        render_template(
            "donors/search.html",
            filters=filters,
            errors=errors,
            pagination=pagination,
            has_filters=has_filters,
        ),
        400 if errors else 200,
    )


@bp.route("/donors/<int:profile_id>")
@role_required(ROLE_RECIPIENT)
def detail(profile_id):
    profile = donors.get_public_profile(profile_id)
    if profile is None:
        abort(404)
    existing = contacts.latest_between(current_user, profile.user_id)
    return render_template("donors/detail.html", profile=profile, existing=existing)
