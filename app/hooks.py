"""Per-request hooks: request IDs, security headers and access logging."""

import time
import uuid

from flask import g, request
from flask_login import current_user

from app.utils.security import apply_security_headers

QUIET_PREFIXES = ("/static/", "/health/")


def register_hooks(app):
    @app.before_request
    def start_request():
        g.request_id = uuid.uuid4().hex[:16]
        g.started = time.perf_counter()

    @app.after_request
    def finish_request(response):
        quiet = request.path.startswith(QUIET_PREFIXES)
        private = False
        user_id = None
        if not quiet:
            try:
                if current_user and current_user.is_authenticated:
                    private = True
                    user_id = current_user.get_id()
            except Exception:  # noqa: BLE001 - never fail a response over logging
                pass
        if request.blueprint == "auth":
            private = True
        apply_security_headers(
            response, secure_transport=request.is_secure, private=private
        )
        response.headers["X-Request-ID"] = g.get("request_id", "-")
        if not quiet:
            elapsed = time.perf_counter() - g.get("started", time.perf_counter())
            app.logger.info(
                "request",
                extra={
                    "request_id": g.get("request_id"),
                    "method": request.method,
                    "path": request.path,
                    "status": response.status_code,
                    "duration_ms": round(elapsed * 1000, 1),
                    "user_id": user_id,
                },
            )
        return response
