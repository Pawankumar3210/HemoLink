"""Initial schema: users, donor profiles, requests, contacts, notifications.

Revision ID: 7c1f2a9d4b10
Revises:
Create Date: 2026-11-21 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "7c1f2a9d4b10"
down_revision = None
branch_labels = None
depends_on = None

BLOOD_GROUPS = "'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'"
AVAILABILITY = "'available', 'temporarily_unavailable', 'unavailable'"
REQUEST_STATUSES = "'open', 'fulfilled', 'cancelled', 'rejected'"
URGENCY = "'normal', 'high', 'urgent'"
CONTACT_STATUSES = "'pending', 'accepted', 'declined', 'withdrawn'"


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column(
            "account_status",
            sa.String(length=20),
            server_default="active",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "role IN ('donor', 'recipient', 'admin')", name="ck_users_role"
        ),
        sa.CheckConstraint(
            "account_status IN ('active', 'suspended', 'deleted')",
            name="ck_users_account_status",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index(
        "ix_users_role_account_status", "users", ["role", "account_status"]
    )
    op.create_index("ix_users_created_at", "users", ["created_at"])

    op.create_table(
        "donor_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("blood_group", sa.String(length=3), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("gender", sa.String(length=20), nullable=True),
        sa.Column("state", sa.String(length=80), nullable=False),
        sa.Column("city", sa.String(length=80), nullable=False),
        sa.Column("last_donation_date", sa.Date(), nullable=True),
        sa.Column(
            "availability_status",
            sa.String(length=30),
            server_default="available",
            nullable=False,
        ),
        sa.Column(
            "visible_in_search",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "share_last_donation_date",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "blood_group IN (%s)" % BLOOD_GROUPS, name="ck_donor_profiles_blood_group"
        ),
        sa.CheckConstraint(
            "availability_status IN (%s)" % AVAILABILITY,
            name="ck_donor_profiles_availability",
        ),
        sa.CheckConstraint("age >= 18 AND age <= 65", name="ck_donor_profiles_age"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_donor_profiles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_donor_profiles")),
        sa.UniqueConstraint("user_id", name="uq_donor_profiles_user_id"),
    )
    op.create_index(
        "ix_donor_profiles_search",
        "donor_profiles",
        ["visible_in_search", "blood_group", "state", "city"],
    )
    op.create_index(
        "ix_donor_profiles_availability", "donor_profiles", ["availability_status"]
    )

    op.create_table(
        "blood_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("requester_id", sa.Integer(), nullable=False),
        sa.Column("blood_group", sa.String(length=3), nullable=False),
        sa.Column("units_required", sa.Integer(), nullable=False),
        sa.Column("hospital_name", sa.String(length=150), nullable=True),
        sa.Column("state", sa.String(length=80), nullable=False),
        sa.Column("city", sa.String(length=80), nullable=False),
        sa.Column("required_by", sa.Date(), nullable=False),
        sa.Column(
            "urgency", sa.String(length=10), server_default="normal", nullable=False
        ),
        sa.Column(
            "status", sa.String(length=15), server_default="open", nullable=False
        ),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("moderation_note", sa.String(length=200), nullable=True),
        sa.Column("status_changed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "blood_group IN (%s)" % BLOOD_GROUPS, name="ck_blood_requests_blood_group"
        ),
        sa.CheckConstraint(
            "urgency IN (%s)" % URGENCY, name="ck_blood_requests_urgency"
        ),
        sa.CheckConstraint(
            "status IN (%s)" % REQUEST_STATUSES, name="ck_blood_requests_status"
        ),
        sa.CheckConstraint(
            "units_required >= 1 AND units_required <= 20",
            name="ck_blood_requests_units",
        ),
        sa.ForeignKeyConstraint(
            ["requester_id"],
            ["users.id"],
            name=op.f("fk_blood_requests_requester_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blood_requests")),
    )
    op.create_index(
        "ix_blood_requests_requester", "blood_requests", ["requester_id", "status"]
    )
    op.create_index(
        "ix_blood_requests_discovery",
        "blood_requests",
        ["status", "blood_group", "state", "city"],
    )
    op.create_index("ix_blood_requests_created_at", "blood_requests", ["created_at"])

    op.create_table(
        "contact_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("donor_id", sa.Integer(), nullable=False),
        sa.Column("recipient_id", sa.Integer(), nullable=False),
        sa.Column("blood_request_id", sa.Integer(), nullable=True),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column(
            "status", sa.String(length=15), server_default="pending", nullable=False
        ),
        sa.Column("donor_consent_at", sa.DateTime(), nullable=True),
        sa.Column("recipient_access_revoked_at", sa.DateTime(), nullable=True),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN (%s)" % CONTACT_STATUSES, name="ck_contact_requests_status"
        ),
        sa.ForeignKeyConstraint(
            ["blood_request_id"],
            ["blood_requests.id"],
            name=op.f("fk_contact_requests_blood_request_id_blood_requests"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["donor_id"],
            ["users.id"],
            name=op.f("fk_contact_requests_donor_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_id"],
            ["users.id"],
            name=op.f("fk_contact_requests_recipient_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contact_requests")),
    )
    op.create_index(
        "ix_contact_requests_pair",
        "contact_requests",
        ["donor_id", "recipient_id", "blood_request_id"],
    )
    op.create_index(
        "ix_contact_requests_donor_status", "contact_requests", ["donor_id", "status"]
    )
    op.create_index(
        "ix_contact_requests_recipient_status",
        "contact_requests",
        ["recipient_id", "status"],
    )
    op.create_index(
        "ix_contact_requests_created_at", "contact_requests", ["created_at"]
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("related_type", sa.String(length=30), nullable=True),
        sa.Column("related_id", sa.Integer(), nullable=True),
        sa.Column(
            "is_read", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notifications_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_index(
        "ix_notifications_user_read",
        "notifications",
        ["user_id", "is_read", "created_at"],
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("details", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_audit_logs_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_logs_actor", "audit_logs", ["actor_id", "created_at"])
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_password_reset_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_reset_tokens")),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_tokens_token_hash"),
    )
    op.create_index(
        "ix_password_reset_tokens_user", "password_reset_tokens", ["user_id"]
    )


def downgrade():
    op.drop_table("password_reset_tokens")
    op.drop_table("audit_logs")
    op.drop_table("notifications")
    op.drop_table("contact_requests")
    op.drop_table("blood_requests")
    op.drop_table("donor_profiles")
    op.drop_table("users")
