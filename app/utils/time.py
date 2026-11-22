"""Time helpers. All timestamps are stored as naive UTC datetimes."""

from datetime import datetime, timezone


def utcnow():
    """Return the current UTC time as a naive datetime (MySQL DATETIME friendly)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
