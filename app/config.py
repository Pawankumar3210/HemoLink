"""Environment-driven configuration. No secrets live in this file."""

import os
import secrets
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()

PLACEHOLDER_SECRETS = {
    "",
    "change-me",
    "changeme",
    "replace-with-a-long-random-string",
}


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def normalize_database_url(url):
    """Accept ``mysql://`` URLs (common on hosts) and force the PyMySQL driver."""
    url = (url or "").strip()
    if url.startswith("mysql://"):
        url = "mysql+pymysql://" + url[len("mysql://") :]
    return url


def engine_options():
    """SQLAlchemy engine options. ``DB_SSL_CA`` enables TLS for managed databases."""
    options = {"pool_pre_ping": True, "pool_recycle": 280}
    if os.environ.get("VERCEL") or os.environ.get("SERVERLESS"):
        from sqlalchemy.pool import NullPool

        options["poolclass"] = NullPool
        options.pop("pool_recycle", None)
    ca_path = os.environ.get("DB_SSL_CA", "").strip()
    if not ca_path and os.environ.get("VERCEL"):
        for candidate in (
            "/etc/ssl/certs/ca-certificates.crt",
            "/etc/pki/tls/certs/ca-bundle.crt",
            "/etc/ssl/cert.pem",
        ):
            if os.path.exists(candidate):
                ca_path = candidate
                break
    if ca_path:
        options["connect_args"] = {"ssl": {"ca": ca_path}}
    return options


class Config:
    """Settings shared by every environment."""

    APP_ENV = "development"
    APP_NAME = "HemoLink"
    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    SQLALCHEMY_DATABASE_URI = normalize_database_url(os.environ.get("DATABASE_URL"))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = engine_options()

    SESSION_COOKIE_NAME = "hemolink_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", False)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    PERMANENT_SESSION_LIFETIME = timedelta(hours=env_int("SESSION_HOURS", 8))

    WTF_CSRF_TIME_LIMIT = None
    MAX_CONTENT_LENGTH = 64 * 1024

    RATELIMIT_ENABLED = env_bool("RATELIMIT_ENABLED", True)
    TRUST_PROXY_HOPS = env_int("TRUST_PROXY_HOPS", 0)

    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOG_JSON = env_bool("LOG_JSON", False)

    PASSWORD_RESET_MINUTES = env_int("PASSWORD_RESET_MINUTES", 30)
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = env_int("MAIL_PORT", 587)
    MAIL_USE_TLS = env_bool("MAIL_USE_TLS", True)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", "HemoLink <no-reply@hemolink.example>")
    # "console" delivery is a development convenience; it is refused in production.
    ALLOW_CONSOLE_MAIL = True

    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "")
    # Identifies the deployed build (Render sets RENDER_GIT_COMMIT automatically).
    RELEASE = (
        os.environ.get("RELEASE_SHA") or os.environ.get("RENDER_GIT_COMMIT") or ""
    )[:12]

    ALLOW_DEMO_SEED = env_bool("ALLOW_DEMO_SEED", False)
    SEARCH_PAGE_SIZE = 9
    TABLE_PAGE_SIZE = 15

    @classmethod
    def finalize(cls, app):
        """Hook for per-environment validation once the app config is final."""
        if not app.config.get("SQLALCHEMY_DATABASE_URI"):
            raise RuntimeError(
                "DATABASE_URL is not set. Copy .env.example to .env and set it, "
                "e.g. mysql+pymysql://user:password@localhost:3306/hemolink"
            )


class DevelopmentConfig(Config):
    APP_ENV = "development"
    DEBUG = env_bool("FLASK_DEBUG", True)

    @classmethod
    def finalize(cls, app):
        super().finalize(app)
        if app.config.get("SECRET_KEY") in PLACEHOLDER_SECRETS:
            app.config["SECRET_KEY"] = secrets.token_hex(32)
            app.logger.warning(
                "SECRET_KEY not set: using a temporary key. Sessions will reset "
                "when the server restarts. Set SECRET_KEY in .env."
            )


class TestingConfig(Config):
    APP_ENV = "testing"
    TESTING = True
    SECRET_KEY = "test-only-key-not-a-secret"
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SQLALCHEMY_DATABASE_URI = normalize_database_url(
        os.environ.get("TEST_DATABASE_URL") or "sqlite:///:memory:"
    )
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    SERVER_NAME = None
    MAIL_SERVER = ""
    ALLOW_DEMO_SEED = True


class ProductionConfig(Config):
    APP_ENV = "production"
    DEBUG = False
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", True)
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    PREFERRED_URL_SCHEME = "https"
    LOG_JSON = env_bool("LOG_JSON", True)
    ALLOW_CONSOLE_MAIL = False

    @classmethod
    def finalize(cls, app):
        super().finalize(app)
        secret = app.config.get("SECRET_KEY") or ""
        if secret in PLACEHOLDER_SECRETS or len(secret) < 32:
            raise RuntimeError(
                "SECRET_KEY must be set to a random value of at least 32 "
                'characters in production (python -c "import secrets; '
                'print(secrets.token_hex(32))").'
            )
        if os.environ.get("VERCEL"):
            app.config.setdefault("TRUST_PROXY_HOPS", 1)


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name=None):
    name = (name or os.environ.get("APP_ENV") or "development").lower()
    try:
        return CONFIGS[name]
    except KeyError:
        raise RuntimeError(
            "Unknown APP_ENV %r. Use one of: %s" % (name, ", ".join(CONFIGS))
        )
