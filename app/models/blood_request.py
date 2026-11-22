"""Blood request model."""

from datetime import date

from app.constants import (
    BLOOD_GROUPS,
    REQUEST_OPEN,
    REQUEST_STATUSES,
    URGENCY_LEVELS,
    URGENCY_NORMAL,
    sql_in,
)
from app.extensions import db
from app.utils.time import utcnow


class BloodRequest(db.Model):
    __tablename__ = "blood_requests"
    __table_args__ = (
        db.Index("ix_blood_requests_requester", "requester_id", "status"),
        db.Index(
            "ix_blood_requests_discovery", "status", "blood_group", "state", "city"
        ),
        db.Index("ix_blood_requests_created_at", "created_at"),
        db.CheckConstraint(
            sql_in("blood_group", BLOOD_GROUPS), name="ck_blood_requests_blood_group"
        ),
        db.CheckConstraint(
            sql_in("urgency", URGENCY_LEVELS), name="ck_blood_requests_urgency"
        ),
        db.CheckConstraint(
            sql_in("status", REQUEST_STATUSES), name="ck_blood_requests_status"
        ),
        db.CheckConstraint(
            "units_required >= 1 AND units_required <= 20",
            name="ck_blood_requests_units",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    blood_group = db.Column(db.String(3), nullable=False)
    units_required = db.Column(db.Integer, nullable=False)
    hospital_name = db.Column(db.String(150), nullable=True)
    state = db.Column(db.String(80), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    required_by = db.Column(db.Date, nullable=False)
    urgency = db.Column(
        db.String(10), nullable=False, default=URGENCY_NORMAL, server_default="normal"
    )
    status = db.Column(
        db.String(15), nullable=False, default=REQUEST_OPEN, server_default="open"
    )
    notes = db.Column(db.String(500), nullable=True)
    moderation_note = db.Column(db.String(200), nullable=True)
    status_changed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    requester = db.relationship("User")

    @property
    def is_open(self):
        return self.status == REQUEST_OPEN

    @property
    def is_overdue(self):
        return self.is_open and self.required_by < date.today()

    def __repr__(self):
        return "<BloodRequest %s %s>" % (self.id, self.status)
