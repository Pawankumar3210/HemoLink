"""Donor profile model (one-to-one with a donor user)."""

from app.constants import AVAILABILITY_STATUSES, AVAILABLE, BLOOD_GROUPS, sql_in
from app.extensions import db
from app.utils.time import utcnow


class DonorProfile(db.Model):
    __tablename__ = "donor_profiles"
    __table_args__ = (
        db.UniqueConstraint("user_id", name="uq_donor_profiles_user_id"),
        db.Index(
            "ix_donor_profiles_search",
            "visible_in_search",
            "blood_group",
            "state",
            "city",
        ),
        db.Index("ix_donor_profiles_availability", "availability_status"),
        db.CheckConstraint(
            sql_in("blood_group", BLOOD_GROUPS), name="ck_donor_profiles_blood_group"
        ),
        db.CheckConstraint(
            sql_in("availability_status", AVAILABILITY_STATUSES),
            name="ck_donor_profiles_availability",
        ),
        db.CheckConstraint("age >= 18 AND age <= 65", name="ck_donor_profiles_age"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    blood_group = db.Column(db.String(3), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(20), nullable=True)
    state = db.Column(db.String(80), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    last_donation_date = db.Column(db.Date, nullable=True)
    availability_status = db.Column(
        db.String(30), nullable=False, default=AVAILABLE, server_default="available"
    )
    visible_in_search = db.Column(
        db.Boolean, nullable=False, default=False, server_default=db.false()
    )
    share_last_donation_date = db.Column(
        db.Boolean, nullable=False, default=False, server_default=db.false()
    )
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    user = db.relationship("User", back_populates="donor_profile")

    @property
    def is_available(self):
        return self.availability_status == AVAILABLE

    @property
    def public_last_donation_date(self):
        """The last donation date, only if the donor opted to share it."""
        return self.last_donation_date if self.share_last_donation_date else None

    def __repr__(self):
        return "<DonorProfile %s %s>" % (self.id, self.blood_group)
