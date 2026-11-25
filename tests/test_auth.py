"""Registration, login, logout, password hashing and password reset."""

from datetime import timedelta

from sqlalchemy import select

from app.extensions import db
from app.models import AuditLog, DonorProfile, Notification, PasswordResetToken, User
from app.utils.security import hash_token
from app.utils.time import utcnow
from tests.helpers import (
    PASSWORD,
    count,
    create_user,
    donor_form,
    extract_token,
    get_email,
    login,
    logged_in_client,
    recipient_form,
)


def user_by_email(app, email):
    with app.app_context():
        user = db.session.scalar(select(User).where(User.email == email))
        if user is not None:
            db.session.expunge(user)
        return user


def test_register_donor_creates_user_profile_and_welcome(app, client):
    response = client.post("/register/donor", data=donor_form())
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")
    user = user_by_email(app, "asha@example.com")
    assert user.role == "donor" and user.account_status == "active"
    assert count(app, DonorProfile, DonorProfile.user_id == user.id) == 1
    assert count(app, Notification, Notification.user_id == user.id) == 1
    assert count(app, AuditLog, AuditLog.action == "user.register") == 1


def test_register_recipient_has_no_donor_profile(app, client):
    response = client.post("/register/recipient", data=recipient_form())
    assert response.status_code == 302
    assert count(app, DonorProfile) == 0
    assert user_by_email(app, "rohan@example.com").role == "recipient"


def test_password_is_hashed_never_plaintext(app, client):
    client.post("/register/recipient", data=recipient_form())
    user = user_by_email(app, "rohan@example.com")
    assert user.password_hash != PASSWORD
    assert PASSWORD not in user.password_hash
    assert user.check_password(PASSWORD)
    assert not user.check_password("wrong-password1")


def test_duplicate_email_rejected(app, client):
    client.post("/register/recipient", data=recipient_form())
    other = app.test_client()
    response = other.post(
        "/register/recipient", data=recipient_form(email="ROHAN@example.com")
    )
    assert response.status_code == 400
    assert b"already exists" in response.data
    assert count(app, User) == 1


def test_invalid_email_and_weak_password_rejected(app, client):
    response = client.post(
        "/register/recipient",
        data=recipient_form(
            email="not-an-email", password="weak", confirm_password="weak"
        ),
    )
    assert response.status_code == 400
    assert b"valid email" in response.data
    assert count(app, User) == 0


def test_registration_requires_terms_and_matching_passwords(app, client):
    response = client.post(
        "/register/recipient",
        data=recipient_form(accept_terms="", confirm_password="Different1pass"),
    )
    assert response.status_code == 400
    assert b"do not match" in response.data and b"Accept the terms" in response.data
    assert count(app, User) == 0


def test_public_registration_cannot_create_admin(app, client):
    response = client.post(
        "/register/recipient", data=recipient_form(role="admin", account_type="admin")
    )
    assert response.status_code == 302
    assert user_by_email(app, "rohan@example.com").role == "recipient"
    assert client.get("/register/admin").status_code == 404


def test_login_redirects_by_role(app):
    for role, expected in (
        ("donor", "/dashboard/donor"),
        ("recipient", "/dashboard/recipient"),
        ("admin", "/admin/"),
    ):
        user_id = create_user(app, role)
        client = app.test_client()
        assert login(client, app, user_id).status_code == 302
        response = client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["Location"].endswith(expected)


def test_login_success_updates_last_login(app, client):
    user_id = create_user(app, "recipient")
    login(client, app, user_id)
    with app.app_context():
        assert db.session.get(User, user_id).last_login_at is not None


def test_invalid_login_gives_generic_message(app, client):
    user_id = create_user(app, "recipient")
    wrong_password = client.post(
        "/login", data={"email": get_email(app, user_id), "password": "Wrong1pass!"}
    )
    unknown_email = client.post(
        "/login", data={"email": "nobody@example.com", "password": "Wrong1pass!"}
    )
    for response in (wrong_password, unknown_email):
        assert response.status_code == 200
        assert b"Invalid email or password." in response.data
    assert wrong_password.data.count(b"Invalid email or password.") == (
        unknown_email.data.count(b"Invalid email or password.")
    )


def test_suspended_user_cannot_login(app, client):
    user_id = create_user(app, "recipient", status="suspended")
    response = client.post(
        "/login", data={"email": get_email(app, user_id), "password": PASSWORD}
    )
    assert response.status_code == 200
    assert b"suspended" in response.data
    assert client.get("/dashboard/recipient").status_code == 302


def test_logout_requires_post_and_ends_session(app):
    user_id = create_user(app, "recipient")
    client = logged_in_client(app, user_id)
    assert client.get("/logout").status_code == 405
    assert client.post("/logout").status_code == 302
    response = client.get("/dashboard/recipient")
    assert response.status_code == 302 and "/login" in response.headers["Location"]


def test_login_next_redirect_is_same_site_only(app, client):
    user_id = create_user(app, "recipient")
    data = {"email": get_email(app, user_id), "password": PASSWORD}
    good = client.post("/login?next=/notifications/", data=data)
    assert good.headers["Location"].endswith("/notifications/")
    client.post("/logout")
    bad = client.post("/login?next=https://evil.example/", data=data)
    assert "evil.example" not in bad.headers["Location"]


def test_protected_pages_require_login(client):
    for path in (
        "/dashboard",
        "/dashboard/donor",
        "/dashboard/recipient",
        "/account",
        "/donors/search",
        "/requests/",
        "/notifications/",
        "/contact/incoming",
        "/admin/",
    ):
        response = client.get(path)
        assert response.status_code == 302, path
        assert "/login" in response.headers["Location"], path


# ---- password reset -------------------------------------------------------


def request_reset(app, client, email):
    return client.post("/forgot-password", data={"email": email})


def test_password_reset_full_flow(app, client):
    user_id = create_user(app, "recipient")
    email = get_email(app, user_id)
    assert request_reset(app, client, email).status_code == 302
    outbox = app.extensions["mail_outbox"]
    assert len(outbox) == 1 and outbox[0]["to"] == email
    token = extract_token(outbox[0]["body"])

    with app.app_context():
        rows = list(db.session.scalars(select(PasswordResetToken)))
        assert len(rows) == 1
        assert rows[0].token_hash == hash_token(token)
        assert token not in rows[0].token_hash

    assert client.get("/reset-password/%s" % token).status_code == 200
    new_password = "Brand9newpass"
    response = client.post(
        "/reset-password/%s" % token,
        data={"password": new_password, "confirm_password": new_password},
    )
    assert response.status_code == 302
    fresh = app.test_client()
    ok = fresh.post("/login", data={"email": email, "password": new_password})
    assert ok.status_code == 302
    old = app.test_client().post("/login", data={"email": email, "password": PASSWORD})
    assert b"Invalid email or password." in old.data


def test_reset_token_is_single_use(app, client):
    user_id = create_user(app, "recipient")
    request_reset(app, client, get_email(app, user_id))
    token = extract_token(app.extensions["mail_outbox"][0]["body"])
    data = {"password": "Brand9newpass", "confirm_password": "Brand9newpass"}
    assert client.post("/reset-password/%s" % token, data=data).status_code == 302
    assert client.post("/reset-password/%s" % token, data=data).status_code == 400
    assert client.get("/reset-password/%s" % token).status_code == 400


def test_expired_reset_token_rejected(app, client):
    user_id = create_user(app, "recipient")
    request_reset(app, client, get_email(app, user_id))
    token = extract_token(app.extensions["mail_outbox"][0]["body"])
    with app.app_context():
        row = db.session.scalar(select(PasswordResetToken))
        row.expires_at = utcnow() - timedelta(minutes=1)
        db.session.commit()
    assert client.get("/reset-password/%s" % token).status_code == 400
    response = client.post(
        "/reset-password/%s" % token,
        data={"password": "Brand9newpass", "confirm_password": "Brand9newpass"},
    )
    assert response.status_code == 400


def test_invalid_reset_token_rejected(client):
    assert client.get("/reset-password/not-a-real-token").status_code == 400


def test_unknown_email_gets_same_response_and_no_email(app, client):
    known = create_user(app, "recipient")
    r1 = request_reset(app, client, get_email(app, known))
    r2 = request_reset(app, client, "nobody@example.com")
    assert r1.status_code == r2.status_code == 302
    assert r1.headers["Location"] == r2.headers["Location"]
    assert len(app.extensions["mail_outbox"]) == 1


def test_new_reset_request_invalidates_earlier_token(app, client):
    user_id = create_user(app, "recipient")
    email = get_email(app, user_id)
    request_reset(app, client, email)
    first = extract_token(app.extensions["mail_outbox"][0]["body"])
    request_reset(app, client, email)
    assert client.get("/reset-password/%s" % first).status_code == 400
    second = extract_token(app.extensions["mail_outbox"][1]["body"])
    assert client.get("/reset-password/%s" % second).status_code == 200


def test_reset_unavailable_when_no_mail_and_console_disabled(app, client):
    app.config["ALLOW_CONSOLE_MAIL"] = False
    try:
        response = client.post("/forgot-password", data={"email": "a@example.com"})
        assert response.status_code == 200
        assert b"not available" in response.data
    finally:
        app.config["ALLOW_CONSOLE_MAIL"] = True


def test_dev_outbox_is_development_admin_only(app, client):
    user_id = create_user(app, "recipient")
    request_reset(app, client, get_email(app, user_id))
    assert client.get("/dev/outbox").status_code == 404
    admin_client = logged_in_client(app, create_user(app, "admin"))
    assert admin_client.get("/dev/outbox").status_code == 200
    assert b"Reset your HemoLink password" in admin_client.get("/dev/outbox").data
    app.config["ALLOW_CONSOLE_MAIL"] = False
    try:
        assert admin_client.get("/dev/outbox").status_code == 404
    finally:
        app.config["ALLOW_CONSOLE_MAIL"] = True


def test_changing_password_invalidates_outstanding_reset_tokens(app):
    user_id = create_user(app, "recipient")
    email = get_email(app, user_id)
    client = app.test_client()
    assert request_reset(app, client, email).status_code == 302
    token = extract_token(app.extensions["mail_outbox"][0]["body"])
    account = logged_in_client(app, user_id)
    assert (
        account.post(
            "/account/password",
            data={
                "current_password": PASSWORD,
                "new_password": "Changed9pass",
                "confirm_password": "Changed9pass",
            },
        ).status_code
        == 302
    )
    assert client.get("/reset-password/%s" % token).status_code == 400
