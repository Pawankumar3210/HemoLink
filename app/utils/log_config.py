"""Structured logging to stdout (JSON in production)."""

import json
import logging
import sys
from datetime import datetime, timezone

EXTRA_FIELDS = ("request_id", "method", "path", "status", "duration_ms", "user_id")


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record."""

    def format(self, record):
        payload = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(app):
    """Route application logs to stdout using the configured level/format."""
    handler = logging.StreamHandler(sys.stdout)
    if app.config.get("LOG_JSON"):
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
    level = getattr(logging, str(app.config.get("LOG_LEVEL", "INFO")).upper(), 20)
    app.logger.handlers.clear()
    app.logger.addHandler(handler)
    app.logger.setLevel(level)
    app.logger.propagate = False
    mail_logger = logging.getLogger("hemolink.mail")
    mail_logger.handlers.clear()
    mail_logger.addHandler(handler)
    mail_logger.setLevel(level)
    mail_logger.propagate = False
