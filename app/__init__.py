"""HemoLink: Connecting Donors. Saving Lives."""

from pathlib import Path

from flask import Flask

__version__ = "1.0.0"


def create_app(config_name=None, overrides=None):
    """Application factory.

    ``config_name`` is one of development, testing or production (defaults to
    the APP_ENV environment variable). ``overrides`` is an optional dict applied
    on top of the chosen configuration, which tests use for custom settings.
    """
    from werkzeug.middleware.proxy_fix import ProxyFix

    from app.config import get_config
    from app.utils.log_config import configure_logging

    config_class = get_config(config_name)
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    if overrides:
        app.config.update(overrides)
    configure_logging(app)
    config_class.finalize(app)

    hops = app.config.get("TRUST_PROXY_HOPS", 0)
    if hops > 0:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops, x_host=hops)

    _init_extensions(app)
    _register_blueprints(app)

    from app.cli import register_cli
    from app.errors import register_error_handlers
    from app.hooks import register_hooks
    from app.template_helpers import register_template_helpers

    register_error_handlers(app)
    register_hooks(app)
    register_template_helpers(app)
    register_cli(app)
    return app


def _init_extensions(app):
    from app import models  # noqa: F401  (registers tables with SQLAlchemy)
    from app.extensions import csrf, db, login_manager, migrate

    db.init_app(app)
    migrations_dir = str(Path(app.root_path).parent / "migrations")
    migrate.init_app(app, db, directory=migrations_dir)
    login_manager.init_app(app)
    csrf.init_app(app)


def _register_blueprints(app):
    from app.admin import bp as admin_bp
    from app.auth import bp as auth_bp
    from app.blood_requests import bp as requests_bp
    from app.contact import bp as contact_bp
    from app.dashboard import bp as dashboard_bp
    from app.donors import bp as donors_bp
    from app.main import bp as main_bp
    from app.notifications import bp as notifications_bp

    for blueprint in (
        main_bp,
        auth_bp,
        dashboard_bp,
        donors_bp,
        requests_bp,
        contact_bp,
        notifications_bp,
        admin_bp,
    ):
        app.register_blueprint(blueprint)
