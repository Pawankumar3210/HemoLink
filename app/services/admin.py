"""Administrator operations: listings, moderation, notices and system info."""

import platform
import sys
import time

import flask
from flask import current_app
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import selectinload

from app import __version__
from app.constants import (
    ACCOUNT_ACTIVE,
    ACCOUNT_SUSPENDED,
    ROLE_ADMIN,
    ROLE_DONOR,
    ROLE_RECIPIENT,
)
from app.extensions import db
from app.models import (
    AuditLog,
    BloodRequest,
    ContactRequest,
    DonorProfile,
    Notification,
    User,
)
from app.services import audit
from app.services.donors import escape_like
from app.services.errors import ServiceError
from app.services.mailer import smtp_configured
from app.services.notifications import notify

STARTED_AT = time.time()


def _like(value):
    return "%" + escape_like(value) + "%"


def list_users(filters, page, per_page):
    stmt = select(User)
    if filters.get("q"):
        pattern = _like(filters["q"])
        stmt = stmt.where(
            or_(
                User.full_name.ilike(pattern, escape="\\"),
                User.email.ilike(pattern, escape="\\"),
            )
        )
    if filters.get("role"):
        stmt = stmt.where(User.role == filters["role"])
    if filters.get("status"):
        stmt = stmt.where(User.account_status == filters["status"])
    stmt = stmt.order_by(User.created_at.desc(), User.id.desc())
    return db.paginate(stmt, page=page, per_page=per_page, error_out=False)


def set_account_status(admin, user_id, new_status):
    """Suspend or reactivate a donor/recipient account and audit the action."""
    user = db.session.get(User, user_id)
    if user is None:
        raise ServiceError("User not found.", status=404)
    if user.role == ROLE_ADMIN:
        raise ServiceError("Administrator accounts cannot be changed here.", status=403)
    if user.account_status == "deleted":
        raise ServiceError("Deleted accounts cannot be changed.", status=409)
    if user.account_status == new_status:
        raise ServiceError("The account is already %s." % new_status, status=409)
    user.account_status = new_status
    audit.record(
        "user.suspend" if new_status == ACCOUNT_SUSPENDED else "user.reactivate",
        "user",
        user.id,
        "status=%s" % new_status,
        actor=admin,
    )
    if new_status == ACCOUNT_ACTIVE:
        notify(user.id, "Account reactivated", "Your HemoLink account is active again.")
    db.session.commit()
    return user


def list_donors(filters, page, per_page):
    stmt = (
        select(DonorProfile)
        .join(User, DonorProfile.user_id == User.id)
        .options(selectinload(DonorProfile.user))
    )
    if filters.get("q"):
        stmt = stmt.where(User.full_name.ilike(_like(filters["q"]), escape="\\"))
    if filters.get("blood_group"):
        stmt = stmt.where(DonorProfile.blood_group == filters["blood_group"])
    if filters.get("availability"):
        stmt = stmt.where(DonorProfile.availability_status == filters["availability"])
    if filters.get("state"):
        stmt = stmt.where(DonorProfile.state == filters["state"])
    if filters.get("city"):
        stmt = stmt.where(
            DonorProfile.city.ilike(escape_like(filters["city"]) + "%", escape="\\")
        )
    stmt = stmt.order_by(DonorProfile.created_at.desc(), DonorProfile.id.desc())
    return db.paginate(stmt, page=page, per_page=per_page, error_out=False)


def list_requests(filters, page, per_page):
    stmt = select(BloodRequest).options(selectinload(BloodRequest.requester))
    if filters.get("status"):
        stmt = stmt.where(BloodRequest.status == filters["status"])
    if filters.get("blood_group"):
        stmt = stmt.where(BloodRequest.blood_group == filters["blood_group"])
    if filters.get("state"):
        stmt = stmt.where(BloodRequest.state == filters["state"])
    if filters.get("city"):
        stmt = stmt.where(
            BloodRequest.city.ilike(escape_like(filters["city"]) + "%", escape="\\")
        )
    stmt = stmt.order_by(BloodRequest.created_at.desc(), BloodRequest.id.desc())
    return db.paginate(stmt, page=page, per_page=per_page, error_out=False)


def list_contacts(filters, page, per_page):
    stmt = select(ContactRequest).options(
        selectinload(ContactRequest.donor), selectinload(ContactRequest.recipient)
    )
    if filters.get("status"):
        stmt = stmt.where(ContactRequest.status == filters["status"])
    stmt = stmt.order_by(ContactRequest.created_at.desc(), ContactRequest.id.desc())
    return db.paginate(stmt, page=page, per_page=per_page, error_out=False)


def list_audit(filters, page, per_page):
    stmt = select(AuditLog).options(selectinload(AuditLog.actor))
    if filters.get("action"):
        pattern = escape_like(filters["action"]) + "%"
        stmt = stmt.where(AuditLog.action.like(pattern, escape="\\"))
    stmt = stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    return db.paginate(stmt, page=page, per_page=per_page, error_out=False)


def recent_audit(limit=6):
    stmt = (
        select(AuditLog)
        .options(selectinload(AuditLog.actor))
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
    )
    return list(db.session.scalars(stmt))


def broadcast_notice(admin, cleaned):
    """Send an in-app notice to every active user in the chosen audience."""
    stmt = select(User.id).where(User.account_status == ACCOUNT_ACTIVE)
    if cleaned["audience"] == "all":
        stmt = stmt.where(User.role.in_([ROLE_DONOR, ROLE_RECIPIENT]))
    else:
        stmt = stmt.where(User.role == cleaned["audience"])
    user_ids = list(db.session.scalars(stmt))
    for user_id in user_ids:
        notify(user_id, cleaned["title"], cleaned["message"])
    audit.record(
        "notice.broadcast",
        "notification",
        None,
        "audience=%s recipients=%d" % (cleaned["audience"], len(user_ids)),
        actor=admin,
    )
    db.session.commit()
    return len(user_ids)


def system_info():
    """Non-sensitive runtime information for the admin System page."""
    try:
        dialect = db.engine.dialect.name
        query = "SELECT sqlite_version()" if dialect == "sqlite" else "SELECT VERSION()"
        version = db.session.execute(text(query)).scalar()
        database = {"status": "connected", "version": str(version)}
    except Exception:  # noqa: BLE001 - report any connectivity problem
        db.session.rollback()
        database = {"status": "unreachable", "version": "unknown"}
    counts = {
        "Users": db.session.scalar(select(func.count()).select_from(User)),
        "Donor profiles": db.session.scalar(
            select(func.count()).select_from(DonorProfile)
        ),
        "Blood requests": db.session.scalar(
            select(func.count()).select_from(BloodRequest)
        ),
        "Contact requests": db.session.scalar(
            select(func.count()).select_from(ContactRequest)
        ),
        "Notifications": db.session.scalar(
            select(func.count()).select_from(Notification)
        ),
        "Audit entries": db.session.scalar(select(func.count()).select_from(AuditLog)),
    }
    config = current_app.config
    return {
        "app_version": __version__,
        "environment": config["APP_ENV"],
        "python": platform.python_version(),
        "flask": flask.__version__,
        "platform": sys.platform,
        "database": database,
        "dialect": db.engine.dialect.name,
        "mail": "SMTP configured" if smtp_configured() else "Not configured",
        "rate_limiting": "On" if config.get("RATELIMIT_ENABLED") else "Off",
        "secure_cookies": "On" if config.get("SESSION_COOKIE_SECURE") else "Off",
        "uptime_minutes": int((time.time() - STARTED_AT) / 60),
        "counts": counts,
    }
