"""Command-line tools: ``flask create-admin``, ``flask seed-demo`` and friends."""

import click
from flask import current_app

from app.services import password_reset, users
from app.services.errors import ServiceError
from app.services.validation import validate_common_account, validate_password


def register_cli(app):
    @app.cli.command("create-admin")
    @click.option("--name", prompt="Full name", help="Administrator's full name.")
    @click.option("--email", prompt="Email", help="Administrator's email address.")
    @click.option("--phone", prompt="Phone", help="Phone number (10-15 digits).")
    @click.option(
        "--password",
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
        envvar="HEMOLINK_ADMIN_PASSWORD",
        help="Prompted securely. For automation, set HEMOLINK_ADMIN_PASSWORD.",
    )
    @click.option(
        "--additional",
        is_flag=True,
        help="Allow creating another administrator when one already exists.",
    )
    def create_admin(name, email, phone, password, additional):
        """Create an administrator account (the only way to get one)."""
        from sqlalchemy import func, select

        from app.constants import ROLE_ADMIN
        from app.extensions import db
        from app.models import User

        existing = db.session.scalar(
            select(func.count()).select_from(User).where(User.role == ROLE_ADMIN)
        )
        if existing and not additional:
            raise click.ClickException(
                "An administrator already exists. Pass --additional to create another."
            )
        cleaned, errors = validate_common_account(
            {
                "full_name": name,
                "email": email,
                "phone": phone,
                "password": password,
                "confirm_password": password,
            }
        )
        if errors:
            raise click.ClickException("; ".join(errors.values()))
        try:
            user = users.create_admin(
                cleaned["full_name"], cleaned["email"], cleaned["phone"], password
            )
        except ServiceError as error:
            raise click.ClickException(error.message)
        click.echo("Administrator created: id=%d email=%s" % (user.id, user.email))

    @app.cli.command("seed-demo")
    @click.option("--reset", is_flag=True, help="Remove existing demo data first.")
    @click.option(
        "--password",
        default=None,
        envvar="DEMO_PASSWORD",
        help="Password for demo accounts (random if omitted).",
    )
    def seed_demo(reset, password):
        """Load clearly-marked synthetic demo data (never in production)."""
        from app import seed

        if not current_app.config.get("ALLOW_DEMO_SEED"):
            raise click.ClickException(
                "Demo seeding is disabled here. Set ALLOW_DEMO_SEED=true in a "
                "non-production environment to enable it."
            )
        if current_app.config.get("APP_ENV") == "production":
            raise click.ClickException("Demo seeding is never allowed in production.")
        if password:
            error = validate_password(password)
            if error:
                raise click.ClickException("Demo password: " + error)
        if reset:
            removed = seed.remove_demo_data()
            click.echo("Removed %d existing demo accounts." % removed)
        try:
            password, summary = seed.seed_demo(password)
        except RuntimeError as error:
            raise click.ClickException(str(error))
        click.echo("Demo data created: %s" % summary)
        domain = seed.DEMO_DOMAIN
        click.echo("Demo accounts: donor01@%s, recipient01@%s" % (domain, domain))
        click.echo("Demo password: %s" % password)

    @app.cli.command("purge-reset-tokens")
    def purge_reset_tokens():
        """Delete expired or used password-reset tokens."""
        click.echo("Removed %d tokens." % password_reset.purge_expired())
