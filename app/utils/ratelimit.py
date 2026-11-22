"""A small in-process sliding-window rate limiter.

Limits are tracked per Gunicorn worker. That is sufficient to slow down
brute-force attempts for this project; a shared store such as Redis would be
the next step for a multi-instance deployment (see docs/architecture.md).
"""

import threading
import time
from collections import defaultdict, deque
from functools import wraps

from flask import current_app, request
from flask_login import current_user
from werkzeug.exceptions import TooManyRequests


class RateLimiter:
    """Thread-safe sliding-window counter keyed by an arbitrary string."""

    def __init__(self):
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()
        self._calls = 0

    def hit(self, key, limit, window, now=None):
        """Record a hit. Return ``(allowed, retry_after_seconds)``."""
        now = time.monotonic() if now is None else now
        with self._lock:
            self._calls += 1
            if self._calls % 1000 == 0:
                self._sweep(now, window)
            bucket = self._hits[key]
            while bucket and now - bucket[0] >= window:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = max(1, int(window - (now - bucket[0])) + 1)
                return False, retry_after
            bucket.append(now)
            return True, 0

    def _sweep(self, now, window):
        stale = [k for k, b in self._hits.items() if not b or now - b[-1] >= window]
        for key in stale:
            del self._hits[key]

    def reset(self):
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def _key_part(key):
    if key == "ip":
        return request.remote_addr or "unknown"
    if key == "user":
        return "u%s" % (current_user.get_id() or "anon")
    if key.startswith("form:"):
        value = request.form.get(key[5:], "")
        return value.strip().lower()[:254]
    raise ValueError("Unknown rate-limit key: %s" % key)


def rate_limit(scope, limit, window, key="ip", methods=("POST",)):
    """Limit ``limit`` requests per ``window`` seconds for matching methods."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            enabled = current_app.config.get("RATELIMIT_ENABLED", True)
            if enabled and request.method in methods:
                bucket = "%s:%s" % (scope, _key_part(key))
                allowed, retry_after = limiter.hit(bucket, limit, window)
                if not allowed:
                    raise TooManyRequests(retry_after=retry_after)
            return view(*args, **kwargs)

        return wrapped

    return decorator
