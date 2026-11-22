"""Import every model so SQLAlchemy metadata (and Alembic) can see them."""

from app.models.audit_log import AuditLog
from app.models.blood_request import BloodRequest
from app.models.contact_request import ContactRequest
from app.models.donor import DonorProfile
from app.models.notification import Notification
from app.models.password_reset import PasswordResetToken
from app.models.user import User

__all__ = [
    "AuditLog",
    "BloodRequest",
    "ContactRequest",
    "DonorProfile",
    "Notification",
    "PasswordResetToken",
    "User",
]
