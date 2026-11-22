"""Command-line tools: create-admin and demo seeding."""

from sqlalchemy import func, select

from app.extensions import db
from app.models import BloodRequest, ContactRequest, DonorProfile, User
from app.seed import DEMO_DOMAIN
from tests.helpers import count

ADMIN_ARGS = [
    "create-admin",
    "--name",
    "Admin One",
    "--email",
    "admin@example.com",
    "--phone",
    "+919876543210",
    "--password",
    "Adm1nPass!word",
]


def run(app, args):
    return app.test_cli_runner().invoke(args=args)


def test_create_admin_creates_hashed_admin(app):
    result = run(app, ADMIN_ARGS)
    assert result.exit_code == 0, result.output
    with app.app_context():
        admin = db.session.scalar(select(User).where(User.role == "admin"))
        assert admin.email == "admin@example.com"
        assert admin.password_hash != "Adm1nPass!word"
        assert admin.check_password("Adm1nPass!word")
    assert "Adm1nPass" not in result.output


def test_create_admin_refuses_duplicates(app):
    assert run(app, ADMIN_ARGS).exit_code == 0
    second = run(app, ADMIN_ARGS)
    assert second.exit_code != 0 and "already exists" in second.output
    same_email = run(app, ADMIN_ARGS + ["--additional"])
    assert same_email.exit_code != 0 and "already exists" in same_email.output
    assert count(app, User, User.role == "admin") == 1


def test_create_additional_admin_with_flag(app):
    run(app, ADMIN_ARGS)
    args = list(ADMIN_ARGS)
    args[args.index("admin@example.com")] = "second@example.com"
    assert run(app, args + ["--additional"]).exit_code == 0
    assert count(app, User, User.role == "admin") == 2


def test_create_admin_validates_input(app):
    args = list(ADMIN_ARGS)
    args[args.index("Adm1nPass!word")] = "weak"
    result = run(app, args)
    assert result.exit_code != 0
    assert count(app, User) == 0


def test_seed_demo_creates_marked_synthetic_data(app):
    result = run(app, ["seed-demo", "--password", "Demo1234pass"])
    assert result.exit_code == 0, result.output
    assert count(app, DonorProfile) == 24
    assert count(app, BloodRequest) == 6 and count(app, ContactRequest) == 5
    with app.app_context():
        emails = list(db.session.scalars(select(User.email)))
        assert emails and all(e.endswith("@" + DEMO_DOMAIN) for e in emails)
        # all eight blood groups are represented
        groups = db.session.scalar(
            select(func.count(func.distinct(DonorProfile.blood_group)))
        )
        assert groups == 8
        phones = list(db.session.scalars(select(User.phone)))
        assert all(p.startswith("+910000") for p in phones)


def test_seed_is_repeatable_only_with_reset(app):
    assert run(app, ["seed-demo", "--password", "Demo1234pass"]).exit_code == 0
    again = run(app, ["seed-demo", "--password", "Demo1234pass"])
    assert again.exit_code != 0 and "already exists" in again.output
    reset = run(app, ["seed-demo", "--reset", "--password", "Demo1234pass"])
    assert reset.exit_code == 0 and count(app, DonorProfile) == 24


def test_seed_never_touches_real_accounts(app):
    from tests.helpers import create_user

    real = create_user(app, "donor", email="real.person@example.com")
    run(app, ["seed-demo", "--password", "Demo1234pass"])
    run(app, ["seed-demo", "--reset", "--password", "Demo1234pass"])
    with app.app_context():
        assert db.session.get(User, real) is not None


def test_seed_disabled_unless_allowed(app):
    app.config["ALLOW_DEMO_SEED"] = False
    try:
        result = run(app, ["seed-demo"])
        assert result.exit_code != 0 and "disabled" in result.output
    finally:
        app.config["ALLOW_DEMO_SEED"] = True


def test_seed_refused_in_production_environment(app):
    app.config["APP_ENV"] = "production"
    try:
        result = run(app, ["seed-demo"])
        assert result.exit_code != 0 and "production" in result.output
    finally:
        app.config["APP_ENV"] = "testing"


def test_demo_accounts_can_sign_in_and_search_works(app):
    run(app, ["seed-demo", "--password", "Demo1234pass"])
    client = app.test_client()
    response = client.post(
        "/login",
        data={"email": "recipient01@" + DEMO_DOMAIN, "password": "Demo1234pass"},
    )
    assert response.status_code == 302
    results = client.get("/donors/search", query_string={"blood_group": "O+"})
    assert results.status_code == 200 and b"donor-card" in results.data


def test_purge_reset_tokens_command(app):
    result = run(app, ["purge-reset-tokens"])
    assert result.exit_code == 0 and "Removed 0 tokens" in result.output
