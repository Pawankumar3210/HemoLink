"""Donor profile management and donor search."""

from sqlalchemy import case, select
from sqlalchemy.orm import selectinload

from app.constants import (
    ACCOUNT_ACTIVE,
    AVAILABLE,
    ROLE_DONOR,
    TEMPORARILY_UNAVAILABLE,
)
from app.extensions import db
from app.models import DonorProfile, User
from app.services.errors import ServiceError
from app.services.users import DONOR_FIELDS


def escape_like(value):
    """Escape LIKE wildcards so user input is matched literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def update_profile(user, cleaned):
    """Create or update the donor's profile from validated data."""
    profile = user.donor_profile
    if profile is None:
        profile = DonorProfile(user_id=user.id, **{k: cleaned[k] for k in DONOR_FIELDS})
        db.session.add(profile)
    else:
        for field in DONOR_FIELDS:
            setattr(profile, field, cleaned[field])
    db.session.commit()
    return profile


def set_availability(user, status, visible_in_search=None):
    profile = user.donor_profile
    if profile is None:
        raise ServiceError("Complete your donor profile first.", status=409)
    profile.availability_status = status
    if visible_in_search is not None:
        profile.visible_in_search = visible_in_search
    db.session.commit()
    return profile


def _visible_donors():
    """Base query: donors who opted in and whose account is active."""
    return (
        select(DonorProfile)
        .join(User, DonorProfile.user_id == User.id)
        .where(
            DonorProfile.visible_in_search.is_(True),
            User.account_status == ACCOUNT_ACTIVE,
            User.role == ROLE_DONOR,
        )
    )


def search_donors(filters, page, per_page=9):
    """Filter donors in SQL and return a pagination object."""
    stmt = _visible_donors()
    if filters.get("blood_group"):
        stmt = stmt.where(DonorProfile.blood_group == filters["blood_group"])
    if filters.get("state"):
        stmt = stmt.where(DonorProfile.state == filters["state"])
    if filters.get("city"):
        pattern = escape_like(filters["city"]) + "%"
        stmt = stmt.where(DonorProfile.city.ilike(pattern, escape="\\"))
    if filters.get("availability"):
        stmt = stmt.where(DonorProfile.availability_status == filters["availability"])
    if filters.get("q"):
        pattern = "%" + escape_like(filters["q"]) + "%"
        stmt = stmt.where(User.full_name.ilike(pattern, escape="\\"))

    sort = filters.get("sort", "availability")
    if sort == "name":
        order = (User.full_name.asc(), DonorProfile.id.asc())
    elif sort == "newest":
        order = (DonorProfile.created_at.desc(), DonorProfile.id.desc())
    else:
        rank = case(
            (DonorProfile.availability_status == AVAILABLE, 0),
            (DonorProfile.availability_status == TEMPORARILY_UNAVAILABLE, 1),
            else_=2,
        )
        order = (rank.asc(), User.full_name.asc(), DonorProfile.id.asc())
    stmt = stmt.options(selectinload(DonorProfile.user)).order_by(*order)
    return db.paginate(stmt, page=page, per_page=per_page, error_out=False)


def get_public_profile(profile_id):
    """Return a donor profile only if it may appear in public search."""
    stmt = _visible_donors().where(DonorProfile.id == profile_id)
    return db.session.scalar(stmt)
