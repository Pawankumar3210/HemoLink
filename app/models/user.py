"""User account model."""

from flask import current_app, session
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.constants import (
    ACCOUNT_ACTIVE,
    ACCOUNT_STATUSES,
    ROLE_ADMIN,
    ROLE_DONOR,
    ROLE_RECIPIENT,
    ROLES,
    sql_in,
)
from app.extensions import db, login_manager
from app.utils.time import utcnow


class User(UserMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = (
        db.UniqueConstraint("email", name="uq_users_email"),
        db.Index("ix_users_role_account_status", "role", "account_status"),
        db.Index("ix_users_created_at", "created_at"),
        db.CheckConstraint(sql_in("role", ROLES), name="ck_users_role"),
        db.CheckConstraint(
            sql_in("account_status", ACCOUNT_STATUSES), name="ck_users_account_status"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    account_status = db.Column(
        db.String(20), nullable=False, default=ACCOUNT_ACTIVE, server_default="active"
    )
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)

    donor_profile = db.relationship(
        "DonorProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):
        """Flask-Login hook: only active accounts may sign in."""
        return self.account_status == ACCOUNT_ACTIVE

    @property
    def is_admin(self):
        return self.role == ROLE_ADMIN

    @property
    def is_donor(self):
        return self.role == ROLE_DONOR

    @property
    def is_recipient(self):
        return self.role == ROLE_RECIPIENT

    def __repr__(self):
        return "<User %s %s>" % (self.id, self.role)


@login_manager.user_loader
def load_user(user_id):
    """Reload the user for each request; suspended/deleted users are signed out."""
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return None
    try:
        user = db.session.get(User, uid)
    except Exception:  # noqa: BLE001 - demo DB may be cold/reset on serverless
        db.session.rollback()
        user = None
    if current_app.config.get("ALLOW_DEMO_LOGIN"):
        demo_email = session.get("demo_email")
        demo_password = current_app.config.get("DEMO_LOGIN_PASSWORD") or "demo1234"
        if demo_email and (user is None or user.email != demo_email):
            from app.services import users

            try:
                db.create_all()
            except Exception:  # noqa: BLE001
                db.session.rollback()
            recovered, _ = users.demo_login(demo_email, demo_password, demo_password)
            if recovered:
                session["_user_id"] = recovered.get_id()
                session.modified = True
                return recovered
    if user is None or user.account_status != ACCOUNT_ACTIVE:
        return None
    return user
