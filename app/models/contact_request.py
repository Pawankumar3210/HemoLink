"""Consent-based contact request between a recipient and a donor."""

from app.constants import (
    CONTACT_ACCEPTED,
    CONTACT_PENDING,
    CONTACT_STATUSES,
    sql_in,
)
from app.extensions import db
from app.utils.time import utcnow


class ContactRequest(db.Model):
    __tablename__ = "contact_requests"
    __table_args__ = (
        db.Index(
            "ix_contact_requests_pair",
            "donor_id",
            "recipient_id",
            "blood_request_id",
        ),
        db.Index("ix_contact_requests_donor_status", "donor_id", "status"),
        db.Index("ix_contact_requests_recipient_status", "recipient_id", "status"),
        db.Index("ix_contact_requests_created_at", "created_at"),
        db.CheckConstraint(
            sql_in("status", CONTACT_STATUSES), name="ck_contact_requests_status"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    recipient_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    blood_request_id = db.Column(
        db.Integer, db.ForeignKey("blood_requests.id", ondelete="SET NULL")
    )
    message = db.Column(db.String(500), nullable=False)
    status = db.Column(
        db.String(15), nullable=False, default=CONTACT_PENDING, server_default="pending"
    )
    donor_consent_at = db.Column(db.DateTime, nullable=True)
    recipient_access_revoked_at = db.Column(db.DateTime, nullable=True)
    responded_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    donor = db.relationship("User", foreign_keys=[donor_id])
    recipient = db.relationship("User", foreign_keys=[recipient_id])
    blood_request = db.relationship("BloodRequest")

    @property
    def is_pending(self):
        return self.status == CONTACT_PENDING

    @property
    def access_revoked(self):
        return self.recipient_access_revoked_at is not None

    @property
    def recipient_can_view_contact(self):
        """True only while the donor's consent stands and the donor is active."""
        return (
            self.status == CONTACT_ACCEPTED
            and self.donor_consent_at is not None
            and self.recipient_access_revoked_at is None
            and self.donor is not None
            and self.donor.is_active
        )

    def __repr__(self):
        return "<ContactRequest %s %s>" % (self.id, self.status)
