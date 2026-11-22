"""Small security helpers: safe redirects, token hashing, response headers."""

import hashlib
import secrets
from urllib.parse import urlparse

CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)


def is_safe_redirect_target(target):
    """Allow only same-site relative paths (blocks open redirects)."""
    if not target or not isinstance(target, str):
        return False
    if not target.startswith("/") or target.startswith("//"):
        return False
    if "\\" in target or "\n" in target or "\r" in target:
        return False
    parsed = urlparse(target)
    return not parsed.scheme and not parsed.netloc


def generate_token():
    """Return a URL-safe random token (sent to the user, never stored as-is)."""
    return secrets.token_urlsafe(32)


def hash_token(token):
    """Return the SHA-256 hex digest used to store a token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def apply_security_headers(response, secure_transport=False, private=False):
    """Attach defensive HTTP headers to a response."""
    headers = response.headers
    headers.setdefault("Content-Security-Policy", CSP)
    headers.setdefault("X-Content-Type-Options", "nosniff")
    headers.setdefault("X-Frame-Options", "DENY")
    headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    if secure_transport:
        headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    if private:
        headers["Cache-Control"] = "no-store"
    return response
