"""Email delivery: real SMTP when configured, safe behaviour when it fails."""

import pytest

from tests.helpers import create_user, get_email


class FakeSMTP:
    events = []
    fail = False

    def __init__(self, host, port, timeout=None):
        if FakeSMTP.fail:
            raise OSError("connection refused")
        FakeSMTP.events.append(("connect", host, port))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        FakeSMTP.events.append(("starttls",))

    def login(self, username, password):
        FakeSMTP.events.append(("login", username))

    def send_message(self, message):
        FakeSMTP.events.append(("send", message["To"], message["Subject"]))


@pytest.fixture()
def smtp_app(app, monkeypatch):
    FakeSMTP.events = []
    FakeSMTP.fail = False
    monkeypatch.setattr("app.services.mailer.smtplib.SMTP", FakeSMTP)
    old = {k: app.config[k] for k in ("MAIL_SERVER", "MAIL_USERNAME", "MAIL_PASSWORD")}
    app.config.update(
        MAIL_SERVER="smtp.example.test", MAIL_USERNAME="mailer", MAIL_PASSWORD="pw"
    )
    yield app
    app.config.update(old)


def test_reset_email_sent_over_smtp_with_tls_and_login(smtp_app):
    email = get_email(smtp_app, create_user(smtp_app, "recipient"))
    response = smtp_app.test_client().post("/forgot-password", data={"email": email})
    assert response.status_code == 302
    events = FakeSMTP.events
    assert ("connect", "smtp.example.test", 587) in events
    assert ("starttls",) in events and ("login", "mailer") in events
    assert ("send", email, "Reset your HemoLink password") in events
    assert "mail_outbox" not in smtp_app.extensions  # nothing captured in the console


def test_smtp_failure_does_not_crash_or_reveal_details(smtp_app):
    FakeSMTP.fail = True
    email = get_email(smtp_app, create_user(smtp_app, "recipient"))
    response = smtp_app.test_client().post("/forgot-password", data={"email": email})
    assert response.status_code == 302


def test_dev_outbox_hidden_when_smtp_configured(smtp_app):
    assert smtp_app.test_client().get("/dev/outbox").status_code == 404


def test_health_reports_release_when_configured(app, client):
    app.config["RELEASE"] = "abc1234def56"
    try:
        body = client.get("/health/live").get_json()
    finally:
        app.config["RELEASE"] = ""
    assert body == {"status": "ok", "release": "abc1234def56"}
