"""Account lifecycle: registration, authentication, settings and deletion."""

import secrets

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.constants import (
    ACCOUNT_ACTIVE,
    ACCOUNT_DELETED,
    ACCOUNT_SUSPENDED,
    CONTACT_ACCEPTED,
    CONTACT_DECLINED,
    CONTACT_PENDING,
    CONTACT_WITHDRAWN,
    REQUEST_CANCELLED,
    REQUEST_OPEN,
    ROLE_ADMIN,
    ROLE_DONOR,
    ROLE_RECIPIENT,
)
from app.extensions import db
from app.models import (
    BloodRequest,
    ContactRequest,
    DonorProfile,
    Notification,
    PasswordResetToken,
    User,
)
from app.services import audit
from app.services.errors import ServiceError
from app.services.notifications import notify
from app.utils.time import utcnow

# Used to keep response time similar when an email address is unknown.
_DUMMY_HASH = generate_password_hash("not-a-real-password")

DONOR_FIELDS = (
    "blood_group",
    "age",
    "gender",
    "state",
    "city",
    "last_donation_date",
    "availability_status",
    "visible_in_search",
    "share_last_donation_date",
)


def get_user_by_email(email):
    return db.session.scalar(select(User).where(User.email == email))


def register_user(cleaned, role):
    """Create a donor or recipient account (and donor profile) atomically."""
    if get_user_by_email(cleaned["email"]) is not None:
        raise ServiceError("An account with this email already exists.", field="email")
    user = User(
        full_name=cleaned["full_name"],
        email=cleaned["email"],
        phone=cleaned["phone"],
        role=role,
    )
    user.set_password(cleaned["password"])
    if role == ROLE_DONOR:
        user.donor_profile = DonorProfile(**{k: cleaned[k] for k in DONOR_FIELDS})
    db.session.add(user)
    try:
        db.session.flush()
        notify(
            user.id,
            "Welcome to HemoLink",
            "Your account is ready. Complete your profile to get started.",
            related_type="user",
            related_id=user.id,
        )
        audit.record("user.register", "user", user.id, "role=%s" % role, actor=user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ServiceError("An account with this email already exists.", field="email")
    return user


def authenticate(email, password):
    """Check credentials. Returns ``(user, state)``: ok, invalid or suspended."""
    user = get_user_by_email(email)
    if user is None or user.account_status == ACCOUNT_DELETED:
        check_password_hash(_DUMMY_HASH, password)
        return None, "invalid"
    if not user.check_password(password):
        return None, "invalid"
    if user.account_status == ACCOUNT_SUSPENDED:
        return None, "suspended"
    return user, "ok"


def demo_login(email, password, demo_password, role=None):
    """Create or return a demo user for frictionless demo deployments."""
    if not email or password != demo_password:
        check_password_hash(_DUMMY_HASH, password or "")
        return None, "invalid"
    email = email.lower()
    user = get_user_by_email(email)
    if user:
        if user.account_status == ACCOUNT_DELETED:
            return None, "invalid"
        if user.account_status == ACCOUNT_SUSPENDED:
            user.account_status = ACCOUNT_ACTIVE
            db.session.commit()
        return user, "demo"
    local = (email.split("@", 1)[0] or "demo").replace(".", " ").replace("_", " ")
    name = (
        " ".join(part.capitalize() for part in local.split() if part)[:100]
        or "Demo User"
    )
    if role not in (ROLE_DONOR, ROLE_RECIPIENT):
        role = ROLE_DONOR if "recipient" not in email.lower() else ROLE_RECIPIENT
    user = User(
        full_name=name,
        email=email,
        phone="0000000000",
        role=role,
        account_status=ACCOUNT_ACTIVE,
    )
    user.set_password(secrets.token_hex(16))
    if role == ROLE_DONOR:
        user.donor_profile = DonorProfile(
            blood_group="O+",
            age=25,
            gender="Other",
            state="Delhi",
            city="New Delhi",
            availability_status="available",
            visible_in_search=True,
        )
    db.session.add(user)
    db.session.commit()
    return user, "demo"


def record_login(user):
    user.last_login_at = utcnow()
    db.session.commit()


def update_account(user, cleaned):
    user.full_name = cleaned["full_name"]
    user.phone = cleaned["phone"]
    db.session.commit()


def change_password(user, current_password, new_password):
    if not user.check_password(current_password):
        raise ServiceError("Your current password is incorrect.", "current_password")
    now = utcnow()
    db.session.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)
        )
        .values(used_at=now)
    )
    user.set_password(new_password)
    audit.record("user.password_change", "user", user.id, actor=user)
    db.session.commit()


def delete_account(user, password):
    """Deactivate and anonymise the account (see docs/architecture.md).

    Personal details are removed; blood requests and contact requests are kept
    in anonymised form so counterparties keep a consistent history.
    """
    if user.role == ROLE_ADMIN:
        raise ServiceError("Administrator accounts cannot be deleted here.")
    if not user.check_password(password):
        raise ServiceError("Your password is incorrect.", "password")
    now = utcnow()
    user_id = user.id

    db.session.execute(
        update(BloodRequest)
        .where(
            BloodRequest.requester_id == user_id,
            BloodRequest.status == REQUEST_OPEN,
        )
        .values(status=REQUEST_CANCELLED, status_changed_at=now)
    )
    db.session.execute(
        update(ContactRequest)
        .where(
            ContactRequest.recipient_id == user_id,
            ContactRequest.status == CONTACT_PENDING,
        )
        .values(status=CONTACT_WITHDRAWN, responded_at=now)
    )
    db.session.execute(
        update(ContactRequest)
        .where(
            ContactRequest.donor_id == user_id,
            ContactRequest.status == CONTACT_PENDING,
        )
        .values(status=CONTACT_DECLINED, responded_at=now)
    )
    db.session.execute(
        update(ContactRequest)
        .where(
            ContactRequest.donor_id == user_id,
            ContactRequest.status == CONTACT_ACCEPTED,
            ContactRequest.recipient_access_revoked_at.is_(None),
        )
        .values(recipient_access_revoked_at=now)
    )
    db.session.execute(
        PasswordResetToken.__table__.delete().where(
            PasswordResetToken.user_id == user_id
        )
    )
    db.session.execute(
        Notification.__table__.delete().where(Notification.user_id == user_id)
    )
    if user.donor_profile is not None:
        db.session.delete(user.donor_profile)

    user.full_name = "Deleted user"
    user.email = "deleted-%d@deleted.invalid" % user_id
    user.phone = None
    user.password_hash = generate_password_hash(secrets.token_hex(32))
    user.account_status = ACCOUNT_DELETED
    audit.record("user.delete", "user", user_id, actor=user)
    db.session.commit()


def create_admin(full_name, email, phone, password):
    """Create an administrator (used only by the ``flask create-admin`` command)."""
    if get_user_by_email(email) is not None:
        raise ServiceError("A user with this email already exists.", "email")
    user = User(full_name=full_name, email=email, phone=phone, role=ROLE_ADMIN)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    audit.record("admin.create", "user", user.id, "created via CLI", actor=user)
    db.session.commit()
    return user
