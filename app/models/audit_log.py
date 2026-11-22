"""Audit trail of administrative and security-relevant actions."""

from app.extensions import db
from app.utils.time import utcnow


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    __table_args__ = (
        db.Index("ix_audit_logs_created_at", "created_at"),
        db.Index("ix_audit_logs_actor", "actor_id", "created_at"),
        db.Index("ix_audit_logs_entity", "entity_type", "entity_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    action = db.Column(db.String(60), nullable=False)
    entity_type = db.Column(db.String(40), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    actor = db.relationship("User")
