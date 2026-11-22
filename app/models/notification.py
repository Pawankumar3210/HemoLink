"""In-app notification model."""

from app.extensions import db
from app.utils.time import utcnow


class Notification(db.Model):
    __tablename__ = "notifications"
    __table_args__ = (
        db.Index("ix_notifications_user_read", "user_id", "is_read", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    related_type = db.Column(db.String(30), nullable=True)
    related_id = db.Column(db.Integer, nullable=True)
    is_read = db.Column(
        db.Boolean, nullable=False, default=False, server_default=db.false()
    )
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User")
