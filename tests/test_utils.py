"""Tests for security helpers, the rate limiter and configuration."""

import pytest

from app import create_app
from app.config import get_config, normalize_database_url
from app.utils.ratelimit import RateLimiter
from app.utils.security import (
    generate_token,
    hash_token,
    is_safe_redirect_target,
)


@pytest.mark.parametrize(
    "target,safe",
    [
        ("/dashboard", True),
        ("/donors/search?blood_group=O%2B", True),
        ("//evil.example", False),
        ("https://evil.example", False),
        ("/\\evil.example", False),
        ("javascript:alert(1)", False),
        ("", False),
        (None, False),
        ("/ok\r\nSet-Cookie: x=1", False),
    ],
)
def test_safe_redirect_targets(target, safe):
    assert is_safe_redirect_target(target) is safe


def test_tokens_are_random_and_hashed():
    a, b = generate_token(), generate_token()
    assert a != b and len(a) >= 40
    assert hash_token(a) != a and len(hash_token(a)) == 64
    assert hash_token(a) == hash_token(a)


def test_rate_limiter_sliding_window():
    limiter = RateLimiter()
    for i in range(3):
        assert limiter.hit("k", 3, 60, now=100 + i)[0] is True
    allowed, retry = limiter.hit("k", 3, 60, now=103)
    assert allowed is False and 1 <= retry <= 60
    assert limiter.hit("other", 3, 60, now=103)[0] is True
    assert limiter.hit("k", 3, 60, now=161)[0] is True
    limiter.reset()
    assert limiter.hit("k", 3, 60, now=0)[0] is True


def test_normalize_database_url():
    assert normalize_database_url("mysql://u:p@h/db").startswith("mysql+pymysql://")
    assert normalize_database_url("mysql+pymysql://u:p@h/db") == (
        "mysql+pymysql://u:p@h/db"
    )
    assert normalize_database_url(None) == ""


def test_unknown_environment_rejected():
    with pytest.raises(RuntimeError):
        get_config("staging")


def test_production_requires_strong_secret_key():
    base = {"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"}
    for secret in ("", "change-me", "short"):
        with pytest.raises(RuntimeError):
            create_app("production", {**base, "SECRET_KEY": secret})


def test_production_cookie_and_logging_defaults():
    app = create_app(
        "production",
        {"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "SECRET_KEY": "k" * 40},
    )
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert app.config["DEBUG"] is False
    assert app.config["ALLOW_CONSOLE_MAIL"] is False


def test_database_url_is_required():
    with pytest.raises(RuntimeError):
        create_app("development", {"SQLALCHEMY_DATABASE_URI": ""})
