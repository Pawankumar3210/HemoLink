"""Pytest fixtures.

Tests run on SQLite in memory by default. In CI, TEST_DATABASE_URL points at a
real MySQL service so the same suite verifies MySQL compatibility.
"""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app import create_app
from app.extensions import db
from app.utils.ratelimit import limiter


def _assert_safe_database(app):
    """Refuse to run the destructive test setup against a non-test database."""
    url = make_url(app.config["SQLALCHEMY_DATABASE_URI"])
    if url.get_backend_name() != "sqlite" and "test" not in (url.database or ""):
        raise RuntimeError(
            "Refusing to run tests: the database name must contain 'test' "
            "(got %r). Tests drop and recreate tables." % url.database
        )


def _build(overrides=None, reset_schema=True):
    """Create a test app. ``reset_schema`` drops and recreates every table.

    With TEST_USE_MIGRATIONS=1 (used in CI) the schema is created by running the
    Alembic migrations, so the migrations themselves are exercised on MySQL.
    """
    app = create_app("testing", overrides)
    _assert_safe_database(app)
    with app.app_context():
        if reset_schema:
            db.drop_all()
            db.session.execute(text("DROP TABLE IF EXISTS alembic_version"))
            db.session.commit()
            if os.environ.get("TEST_USE_MIGRATIONS") == "1":
                from flask_migrate import upgrade

                upgrade()
            else:
                db.create_all()
        else:
            db.create_all()
    return app


@pytest.fixture(scope="session")
def app():
    app = _build()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture(autouse=True)
def clean_state(app):
    """Empty every table after each test so tests stay independent."""
    yield
    with app.app_context():
        db.session.remove()
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()
        db.session.remove()
    app.extensions.pop("mail_outbox", None)
    limiter.reset()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def csrf_app():
    """A separate app with CSRF protection on (the default test app turns it off)."""
    app = _build({"WTF_CSRF_ENABLED": True}, reset_schema=False)
    yield app
    with app.app_context():
        db.session.remove()


@pytest.fixture()
def limited_app():
    """A separate app with rate limiting switched on."""
    app = _build({"RATELIMIT_ENABLED": True}, reset_schema=False)
    yield app
    with app.app_context():
        db.session.remove()
