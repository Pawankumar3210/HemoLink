"""Aggregate statistics computed from live database records."""

from sqlalchemy import func, select

from app.constants import (
    ACCOUNT_ACTIVE,
    ACCOUNT_DELETED,
    ACCOUNT_SUSPENDED,
    AVAILABLE,
    CONTACT_ACCEPTED,
    CONTACT_PENDING,
    REQUEST_FULFILLED,
    REQUEST_OPEN,
    ROLE_DONOR,
    ROLE_RECIPIENT,
    TEMPORARILY_UNAVAILABLE,
)
from app.extensions import db
from app.models import BloodRequest, ContactRequest, DonorProfile, User


def _count(model, *conditions):
    stmt = select(func.count()).select_from(model)
    if conditions:
        stmt = stmt.where(*conditions)
    return db.session.scalar(stmt) or 0


def _donor_availability_count(status):
    stmt = (
        select(func.count())
        .select_from(DonorProfile)
        .join(User, DonorProfile.user_id == User.id)
        .where(
            DonorProfile.availability_status == status,
            User.account_status == ACCOUNT_ACTIVE,
        )
    )
    return db.session.scalar(stmt) or 0


def platform_stats():
    """Numbers for the admin overview. Deleted accounts are not counted as users."""
    not_deleted = User.account_status != ACCOUNT_DELETED
    return {
        "total_users": _count(User, not_deleted),
        "donors": _count(User, User.role == ROLE_DONOR, not_deleted),
        "recipients": _count(User, User.role == ROLE_RECIPIENT, not_deleted),
        "suspended": _count(User, User.account_status == ACCOUNT_SUSPENDED),
        "available_donors": _donor_availability_count(AVAILABLE),
        "temporarily_unavailable_donors": _donor_availability_count(
            TEMPORARILY_UNAVAILABLE
        ),
        "total_requests": _count(BloodRequest),
        "open_requests": _count(BloodRequest, BloodRequest.status == REQUEST_OPEN),
        "fulfilled_requests": _count(
            BloodRequest, BloodRequest.status == REQUEST_FULFILLED
        ),
        "pending_contacts": _count(
            ContactRequest, ContactRequest.status == CONTACT_PENDING
        ),
    }


def landing_stats():
    """Live, honest counts for the public landing page (no fabricated numbers)."""
    return {
        "donors": _count(
            User, User.role == ROLE_DONOR, User.account_status == ACCOUNT_ACTIVE
        ),
        "open_requests": _count(BloodRequest, BloodRequest.status == REQUEST_OPEN),
        "fulfilled_requests": _count(
            BloodRequest, BloodRequest.status == REQUEST_FULFILLED
        ),
    }


def donor_dashboard_stats(user):
    return {
        "pending": _count(
            ContactRequest,
            ContactRequest.donor_id == user.id,
            ContactRequest.status == CONTACT_PENDING,
        ),
        "accepted": _count(
            ContactRequest,
            ContactRequest.donor_id == user.id,
            ContactRequest.status == CONTACT_ACCEPTED,
        ),
        "total": _count(ContactRequest, ContactRequest.donor_id == user.id),
    }


def recipient_dashboard_stats(user):
    mine = BloodRequest.requester_id == user.id
    return {
        "open_requests": _count(
            BloodRequest, mine, BloodRequest.status == REQUEST_OPEN
        ),
        "fulfilled_requests": _count(
            BloodRequest, mine, BloodRequest.status == REQUEST_FULFILLED
        ),
        "pending_contacts": _count(
            ContactRequest,
            ContactRequest.recipient_id == user.id,
            ContactRequest.status == CONTACT_PENDING,
        ),
        "accepted_contacts": _count(
            ContactRequest,
            ContactRequest.recipient_id == user.id,
            ContactRequest.status == CONTACT_ACCEPTED,
            ContactRequest.recipient_access_revoked_at.is_(None),
        ),
    }
