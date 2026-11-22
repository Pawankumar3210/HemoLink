"""Single-use, time-limited password reset tokens (stored as SHA-256 hashes)."""

from app.extensions import db
from app.utils.time import utcnow


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        db.UniqueConstraint("token_hash", name="uq_password_reset_tokens_token_hash"),
        db.Index("ix_password_reset_tokens_user", "user_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash = db.Column(db.String(64), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User")

    @property
    def is_usable(self):
        return self.used_at is None and self.expires_at > utcnow()
