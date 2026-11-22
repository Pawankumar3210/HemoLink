"""Helpers for reading query-string arguments safely."""

from flask import request


def page_arg():
    """Return the ``page`` query argument as a sane positive integer."""
    try:
        page = int(request.args.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    return min(max(page, 1), 10000)


def choice_arg(name, allowed):
    """Return a query argument only if it is one of ``allowed`` (else '')."""
    value = (request.args.get(name) or "").strip()
    return value if value in allowed else ""
