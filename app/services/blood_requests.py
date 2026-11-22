"""Blood request lifecycle and visibility rules."""

from datetime import date

from sqlalchemy import case, select

from app.constants import (
    ACCOUNT_ACTIVE,
    CONTACT_ACCEPTED,
    CONTACT_PENDING,
    LABELS,
    REQUEST_CANCELLED,
    REQUEST_FULFILLED,
    REQUEST_OPEN,
    REQUEST_REJECTED,
    ROLE_ADMIN,
    ROLE_DONOR,
    URGENCY_HIGH,
    URGENCY_URGENT,
)
from app.extensions import db
from app.models import BloodRequest, ContactRequest, User
from app.services import audit
from app.services.errors import ServiceError
from app.services.notifications import notify
from app.utils.time import utcnow

ADMIN_TRANSITIONS = {
    REQUEST_OPEN: {REQUEST_FULFILLED, REQUEST_CANCELLED, REQUEST_REJECTED},
    REQUEST_REJECTED: {REQUEST_OPEN},
}
OWNER_TRANSITIONS = {REQUEST_OPEN: {REQUEST_FULFILLED, REQUEST_CANCELLED}}


def create_request(user, cleaned):
    blood_request = BloodRequest(requester_id=user.id, **cleaned)
    db.session.add(blood_request)
    db.session.commit()
    return blood_request


def update_request(blood_request, cleaned):
    if not blood_request.is_open:
        raise ServiceError("Only open requests can be edited.", status=409)
    for field, value in cleaned.items():
        setattr(blood_request, field, value)
    db.session.commit()
    return blood_request


def can_view(blood_request, user):
    """Owner and admins see everything; donors see open requests only."""
    if user.role == ROLE_ADMIN or blood_request.requester_id == user.id:
        return True
    if user.role == ROLE_DONOR:
        return blood_request.is_open and blood_request.requester.is_active
    return False


def change_status(blood_request, new_status, actor, note=None):
    """Apply a status transition if the actor is allowed to make it."""
    is_admin = actor.role == ROLE_ADMIN
    if not is_admin and blood_request.requester_id != actor.id:
        raise ServiceError("Request not found.", status=404)
    table = ADMIN_TRANSITIONS if is_admin else OWNER_TRANSITIONS
    if new_status not in table.get(blood_request.status, set()):
        raise ServiceError(
            "This request cannot be changed from %s to %s."
            % (
                LABELS[blood_request.status].lower(),
                LABELS[new_status].lower(),
            ),
            status=409,
        )
    blood_request.status = new_status
    blood_request.status_changed_at = utcnow()
    if new_status == REQUEST_REJECTED:
        blood_request.moderation_note = note
    elif new_status == REQUEST_OPEN:
        blood_request.moderation_note = None

    owner_message = "Your %s request in %s is now %s." % (
        blood_request.blood_group,
        blood_request.city,
        LABELS[new_status].lower(),
    )
    if new_status == REQUEST_REJECTED and note:
        owner_message += " Reason: %s" % note
    notify(
        blood_request.requester_id,
        "Blood request %s" % LABELS[new_status].lower(),
        owner_message,
        related_type="blood_request",
        related_id=blood_request.id,
    )
    if new_status != REQUEST_OPEN:
        _notify_linked_donors(blood_request, new_status)
    if is_admin:
        audit.record(
            "request.%s" % new_status,
            "blood_request",
            blood_request.id,
            note,
            actor=actor,
        )
    db.session.commit()
    return blood_request


def _notify_linked_donors(blood_request, new_status):
    stmt = select(ContactRequest.id, ContactRequest.donor_id).where(
        ContactRequest.blood_request_id == blood_request.id,
        ContactRequest.status.in_([CONTACT_PENDING, CONTACT_ACCEPTED]),
    )
    for contact_id, donor_id in db.session.execute(stmt):
        notify(
            donor_id,
            "A linked blood request was closed",
            "A request you were asked to help with is now %s."
            % LABELS[new_status].lower(),
            related_type="contact_request",
            related_id=contact_id,
        )


def list_for_requester(user, status, page, per_page):
    stmt = select(BloodRequest).where(BloodRequest.requester_id == user.id)
    if status:
        stmt = stmt.where(BloodRequest.status == status)
    stmt = stmt.order_by(BloodRequest.created_at.desc(), BloodRequest.id.desc())
    return db.paginate(stmt, page=page, per_page=per_page, error_out=False)


def open_requests_for_donors(filters, page, per_page):
    """Open, not-yet-due requests from active users, most urgent first."""
    urgency_rank = case(
        (BloodRequest.urgency == URGENCY_URGENT, 0),
        (BloodRequest.urgency == URGENCY_HIGH, 1),
        else_=2,
    )
    stmt = (
        select(BloodRequest)
        .join(User, BloodRequest.requester_id == User.id)
        .where(
            BloodRequest.status == REQUEST_OPEN,
            BloodRequest.required_by >= date.today(),
            User.account_status == ACCOUNT_ACTIVE,
        )
    )
    if filters.get("blood_group"):
        stmt = stmt.where(BloodRequest.blood_group == filters["blood_group"])
    if filters.get("state"):
        stmt = stmt.where(BloodRequest.state == filters["state"])
    stmt = stmt.order_by(urgency_rank, BloodRequest.required_by, BloodRequest.id)
    return db.paginate(stmt, page=page, per_page=per_page, error_out=False)


def open_requests_for_user(user):
    stmt = (
        select(BloodRequest)
        .where(
            BloodRequest.requester_id == user.id,
            BloodRequest.status == REQUEST_OPEN,
        )
        .order_by(BloodRequest.required_by)
    )
    return list(db.session.scalars(stmt))
