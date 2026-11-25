"""Consent-based contact workflow between recipients and donors."""

from datetime import timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import selectinload

from app.constants import (
    CONTACT_ACCEPTED,
    CONTACT_DECLINED,
    CONTACT_PENDING,
    CONTACT_WITHDRAWN,
    UNAVAILABLE,
)
from app.extensions import db
from app.models import BloodRequest, ContactRequest
from app.services.donors import get_public_profile
from app.services.errors import ServiceError
from app.services.notifications import notify
from app.utils.time import utcnow

DECLINE_COOLDOWN_DAYS = 7


def _same_purpose(blood_request_id):
    if blood_request_id is None:
        return ContactRequest.blood_request_id.is_(None)
    return ContactRequest.blood_request_id == blood_request_id


def create_contact_request(recipient, profile_id, cleaned):
    """Create a pending contact request, enforcing the duplicate-request rules."""
    profile = get_public_profile(profile_id)
    if profile is None:
        raise ServiceError("This donor is not available for contact.", status=404)
    if profile.availability_status == UNAVAILABLE:
        raise ServiceError("This donor is currently not accepting contact requests.")

    blood_request_id = cleaned["blood_request_id"]
    if blood_request_id is not None:
        linked = db.session.get(BloodRequest, blood_request_id)
        if linked is None or linked.requester_id != recipient.id or not linked.is_open:
            raise ServiceError(
                "Choose one of your open blood requests.", "blood_request_id"
            )

    base = select(ContactRequest.id).where(
        ContactRequest.donor_id == profile.user_id,
        ContactRequest.recipient_id == recipient.id,
        _same_purpose(blood_request_id),
    )
    active = base.where(
        or_(
            ContactRequest.status == CONTACT_PENDING,
            (ContactRequest.status == CONTACT_ACCEPTED)
            & ContactRequest.recipient_access_revoked_at.is_(None),
        )
    )
    if db.session.scalar(active.limit(1)) is not None:
        raise ServiceError(
            "You already have an active contact request with this donor "
            "for this purpose."
        )
    cutoff = utcnow() - timedelta(days=DECLINE_COOLDOWN_DAYS)
    recently_declined = base.where(
        ContactRequest.status == CONTACT_DECLINED,
        ContactRequest.responded_at >= cutoff,
    )
    if db.session.scalar(recently_declined.limit(1)) is not None:
        raise ServiceError(
            "This donor declined a similar request recently. "
            "Please try again in a few days."
        )

    contact = ContactRequest(
        donor_id=profile.user_id,
        recipient_id=recipient.id,
        blood_request_id=blood_request_id,
        message=cleaned["message"],
    )
    db.session.add(contact)
    db.session.flush()
    notify(
        profile.user_id,
        "New contact request",
        "%s would like to contact you about a blood donation." % recipient.full_name,
        related_type="contact_request",
        related_id=contact.id,
    )
    db.session.commit()
    return contact


def _transition_error(contact_id, user_field, user_id):
    """Explain why an atomic status update matched no rows."""
    existing = db.session.get(ContactRequest, contact_id)
    if existing is None or getattr(existing, user_field) != user_id:
        return ServiceError("Contact request not found.", status=404)
    return ServiceError("This request can no longer be changed.", status=409)


def respond(contact_id, donor, accept):
    """Donor accepts or declines. The UPDATE is atomic, so it cannot run twice."""
    now = utcnow()
    values = {
        "status": CONTACT_ACCEPTED if accept else CONTACT_DECLINED,
        "responded_at": now,
        "updated_at": now,
    }
    if accept:
        values["donor_consent_at"] = now
    result = db.session.execute(
        update(ContactRequest)
        .where(
            ContactRequest.id == contact_id,
            ContactRequest.donor_id == donor.id,
            ContactRequest.status == CONTACT_PENDING,
        )
        .values(**values)
    )
    if result.rowcount != 1:
        db.session.rollback()
        raise _transition_error(contact_id, "donor_id", donor.id)
    contact = db.session.get(ContactRequest, contact_id)
    db.session.refresh(contact)
    if accept:
        title = "Contact request accepted"
        message = "%s accepted your request. You can now view their phone number."
    else:
        title = "Contact request declined"
        message = "%s declined your contact request."
    notify(
        contact.recipient_id,
        title,
        message % donor.full_name,
        related_type="contact_request",
        related_id=contact.id,
    )
    db.session.commit()
    return contact


def withdraw(contact_id, recipient):
    now = utcnow()
    result = db.session.execute(
        update(ContactRequest)
        .where(
            ContactRequest.id == contact_id,
            ContactRequest.recipient_id == recipient.id,
            ContactRequest.status == CONTACT_PENDING,
        )
        .values(status=CONTACT_WITHDRAWN, responded_at=now, updated_at=now)
    )
    if result.rowcount != 1:
        db.session.rollback()
        raise _transition_error(contact_id, "recipient_id", recipient.id)
    contact = db.session.get(ContactRequest, contact_id)
    db.session.refresh(contact)
    notify(
        contact.donor_id,
        "Contact request withdrawn",
        "%s withdrew their contact request." % recipient.full_name,
        related_type="contact_request",
        related_id=contact.id,
    )
    db.session.commit()
    return contact


def revoke_access(contact_id, donor):
    """Donor withdraws consent after accepting; the recipient loses the phone number."""
    now = utcnow()
    result = db.session.execute(
        update(ContactRequest)
        .where(
            ContactRequest.id == contact_id,
            ContactRequest.donor_id == donor.id,
            ContactRequest.status == CONTACT_ACCEPTED,
            ContactRequest.recipient_access_revoked_at.is_(None),
        )
        .values(recipient_access_revoked_at=now, updated_at=now)
    )
    if result.rowcount != 1:
        db.session.rollback()
        raise _transition_error(contact_id, "donor_id", donor.id)
    contact = db.session.get(ContactRequest, contact_id)
    db.session.refresh(contact)
    notify(
        contact.recipient_id,
        "Contact access ended",
        "%s ended access to their contact details." % donor.full_name,
        related_type="contact_request",
        related_id=contact.id,
    )
    db.session.commit()
    return contact


def get_for_party(contact_id, user):
    """Return the contact request only if ``user`` is its donor or recipient."""
    contact = db.session.scalar(
        select(ContactRequest)
        .where(ContactRequest.id == contact_id)
        .options(
            selectinload(ContactRequest.donor),
            selectinload(ContactRequest.recipient),
            selectinload(ContactRequest.blood_request),
        )
    )
    if contact is None or user.id not in (contact.donor_id, contact.recipient_id):
        return None
    return contact


def _listing(condition, page, per_page):
    stmt = (
        select(ContactRequest)
        .where(condition)
        .options(
            selectinload(ContactRequest.donor),
            selectinload(ContactRequest.recipient),
            selectinload(ContactRequest.blood_request),
        )
        .order_by(ContactRequest.created_at.desc(), ContactRequest.id.desc())
    )
    return db.paginate(stmt, page=page, per_page=per_page, error_out=False)


def incoming_for_donor(donor, page, per_page=10):
    return _listing(
        (ContactRequest.donor_id == donor.id)
        & (ContactRequest.status == CONTACT_PENDING),
        page,
        per_page,
    )


def history_for_donor(donor, page, per_page=10):
    return _listing(
        (ContactRequest.donor_id == donor.id)
        & (ContactRequest.status != CONTACT_PENDING),
        page,
        per_page,
    )


def list_for_recipient(recipient, page, per_page=10):
    return _listing(ContactRequest.recipient_id == recipient.id, page, per_page)


def latest_between(recipient, donor_user_id):
    """Most recent request from this recipient to this donor (for UI hints)."""
    stmt = (
        select(ContactRequest)
        .where(
            ContactRequest.recipient_id == recipient.id,
            ContactRequest.donor_id == donor_user_id,
        )
        .order_by(ContactRequest.created_at.desc(), ContactRequest.id.desc())
        .limit(1)
    )
    return db.session.scalar(stmt)
