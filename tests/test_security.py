"""CSRF, headers, rate limiting, health checks, error pages and XSS handling."""

import re

from app import create_app
from tests.helpers import (
    PASSWORD,
    create_user,
    donor_form,
    get_email,
    logged_in_client,
    profile_id,
)


def csrf_token(client, path="/login"):
    page = client.get(path)
    match = re.search(rb'name="csrf_token" value="([^"]+)"', page.data)
    assert match, "no CSRF token rendered"
    return match.group(1).decode()


def test_csrf_blocks_post_without_token(csrf_app):
    client = csrf_app.test_client()
    response = client.post("/login", data={"email": "a@example.com", "password": "x"})
    assert response.status_code == 400
    assert b"CSRF" in response.data or b"expired" in response.data


def test_csrf_token_allows_post(csrf_app):
    client = csrf_app.test_client()
    token = csrf_token(client)
    response = client.post(
        "/login",
        data={"email": "a@example.com", "password": "Wrong1pass!", "csrf_token": token},
    )
    assert response.status_code == 200
    assert b"Invalid email or password." in response.data


def test_csrf_protects_state_changing_actions_when_logged_in(csrf_app):
    user_id = create_user(csrf_app, "recipient")
    client = csrf_app.test_client()
    token = csrf_token(client)
    login = client.post(
        "/login",
        data={
            "email": get_email(csrf_app, user_id),
            "password": PASSWORD,
            "csrf_token": token,
        },
    )
    assert login.status_code == 302
    assert client.post("/logout").status_code == 400
    assert client.post("/notifications/read-all").status_code == 400
    assert client.post("/account/delete", data={"password": PASSWORD}).status_code == 400


def test_security_headers_present(client):
    response = client.get("/")
    headers = response.headers
    assert "default-src 'self'" in headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert "Referrer-Policy" in headers and "X-Request-ID" in headers


def test_authenticated_pages_are_not_cached(app):
    client = logged_in_client(app, create_user(app, "recipient"))
    assert client.get("/dashboard/recipient").headers["Cache-Control"] == "no-store"


def test_hsts_only_over_https(client):
    assert "Strict-Transport-Security" not in client.get("/").headers
    secure = client.get("/", base_url="https://localhost")
    assert "Strict-Transport-Security" in secure.headers


def test_session_cookie_flags(app):
    client = app.test_client()
    user_id = create_user(app, "recipient")
    response = client.post(
        "/login", data={"email": get_email(app, user_id), "password": PASSWORD}
    )
    cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie
    assert app.config["SESSION_COOKIE_NAME"] in cookie


def test_login_rate_limited_per_email(limited_app):
    client = limited_app.test_client()
    data = {"email": "target@example.com", "password": "Wrong1pass!"}
    for _ in range(5):
        assert client.post("/login", data=data).status_code == 200
    blocked = client.post("/login", data=data)
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
    assert b"Too many attempts" in blocked.data
    other = client.post("/login", data={**data, "email": "someone@example.com"})
    assert other.status_code == 200


def test_registration_rate_limited(limited_app):
    client = limited_app.test_client()
    for i in range(10):
        response = client.post("/register/recipient", data={"email": "x%d@example.com" % i})
        assert response.status_code == 400
    assert client.post("/register/recipient", data={}).status_code == 429


def test_forgot_password_rate_limited(limited_app):
    client = limited_app.test_client()
    for _ in range(5):
        assert client.post("/forgot-password", data={"email": "a@example.com"}).status_code == 302
    assert client.post("/forgot-password", data={"email": "a@example.com"}).status_code == 429


def test_contact_request_submission_rate_limited(limited_app):
    donor = create_user(limited_app, "donor")
    recipient = create_user(limited_app, "recipient")
    client = logged_in_client(limited_app, recipient)
    path = "/contact/request/%d" % profile_id(limited_app, donor)
    for _ in range(10):
        assert client.post(path, data={"message": "short"}).status_code == 400
    assert client.post(path, data={"message": "short"}).status_code == 429


def test_health_endpoints(client):
    live = client.get("/health/live")
    assert live.status_code == 200 and live.get_json() == {"status": "ok"}
    ready = client.get("/health/ready")
    assert ready.status_code == 200 and ready.get_json() == {"status": "ready"}


def test_readiness_hides_internals_when_database_fails(app, client, monkeypatch):
    from app.extensions import db

    def boom(*args, **kwargs):
        raise RuntimeError("mysql://user:secret@db/hemolink is down")

    monkeypatch.setattr(db.session, "execute", boom)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.get_json() == {"status": "unavailable"}
    assert b"secret" not in response.data


def test_custom_error_pages(app, client):
    missing = client.get("/definitely-not-a-page")
    assert missing.status_code == 404 and b"could not find" in missing.data
    forbidden_client = logged_in_client(app, create_user(app, "recipient"))
    forbidden = forbidden_client.get("/admin/")
    assert forbidden.status_code == 403 and b"do not have access" in forbidden.data


def test_server_errors_do_not_leak_details():
    fresh = create_app("testing", {"PROPAGATE_EXCEPTIONS": False})

    def boom():
        raise RuntimeError("secret database password is hunter2")

    fresh.add_url_rule("/_boom_for_tests", "boom", boom)
    response = fresh.test_client().get("/_boom_for_tests")
    assert response.status_code == 500
    assert b"hunter2" not in response.data and b"Traceback" not in response.data
    assert b"went wrong" in response.data


def test_user_names_are_escaped_everywhere(app):
    create_user(app, "donor", name="Evil <img src=x onerror=alert(1)> Name")
    client = logged_in_client(app, create_user(app, "recipient"))
    page = client.get("/donors/search").data
    assert b"<img src=x" not in page and b"&lt;img src=x" in page


def test_sql_injection_attempts_are_inert(app):
    create_user(app, "donor", name="Normal Nia")
    client = logged_in_client(app, create_user(app, "recipient"))
    for payload in ("' OR '1'='1", "1; DROP TABLE users; --", "%' OR 1=1 --"):
        response = client.get("/donors/search", query_string={"q": payload, "city": payload})
        assert response.status_code == 200 and b"Normal Nia" not in response.data
    bad_login = app.test_client().post(
        "/login", data={"email": "' OR 1=1 --@x.com", "password": "x"}
    )
    assert bad_login.status_code == 200
    assert client.get("/donors/search").status_code == 200


def test_registration_form_is_not_prefilled_with_passwords(client):
    response = client.post("/register/donor", data=donor_form(email="bad", password="Passw0rd!x"))
    assert response.status_code == 400
    assert b'value="Passw0rd!x"' not in response.data


def test_static_assets_served(client):
    assert client.get("/static/css/main.css").status_code == 200
    assert client.get("/static/js/app.js").status_code == 200
    assert client.get("/static/favicon/favicon.svg").status_code == 200
    assert client.get("/static/images/logo-mark.svg").status_code == 200


def test_no_inline_scripts_or_styles_in_public_pages(client):
    for path in ("/", "/about", "/how-it-works", "/sdg-3", "/privacy", "/terms", "/login"):
        html = client.get(path).data.decode()
        assert " style=" not in html, path
        assert not re.search(r"<script(?![^>]*\ssrc=)", html), path
        assert not re.search(r"\son[a-z]+=", html), path
