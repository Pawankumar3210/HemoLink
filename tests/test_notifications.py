"""In-app notifications stored in the database."""

from sqlalchemy import delete

from app.extensions import db
from app.models import Notification
from tests.helpers import (
    create_contact,
    create_user,
    fetch,
    logged_in_client,
    notifications_for,
)


def make_notification(app, user_id, title="Hello", **kwargs):
    with app.app_context():
        notification = Notification(
            user_id=user_id, title=title, message="Body text", **kwargs
        )
        db.session.add(notification)
        db.session.commit()
        return notification.id


def test_unread_count_and_list(app):
    user_id = create_user(app, "recipient")
    make_notification(app, user_id, "First")
    make_notification(app, user_id, "Second")
    client = logged_in_client(app, user_id)
    response = client.get("/notifications/")
    assert response.status_code == 200
    assert b"First" in response.data and b"Second" in response.data
    assert b'class="count-pill"' in response.data


def test_empty_state(app):
    user_id = create_user(app, "recipient")
    with app.app_context():
        db.session.execute(delete(Notification))
        db.session.commit()
    client = logged_in_client(app, user_id)
    assert b"all caught up" in client.get("/notifications/").data


def test_mark_one_and_all_read(app):
    user_id = create_user(app, "recipient")
    first = make_notification(app, user_id, "One")
    make_notification(app, user_id, "Two")
    client = logged_in_client(app, user_id)
    assert client.post("/notifications/%d/read" % first).status_code == 302
    assert fetch(app, Notification, first).is_read is True
    unread = [n for n in notifications_for(app, user_id) if not n.is_read]
    assert unread
    client.post("/notifications/read-all")
    assert all(n.is_read for n in notifications_for(app, user_id))


def test_cannot_mark_another_users_notification(app):
    owner = create_user(app, "recipient")
    other = create_user(app, "recipient")
    notification_id = make_notification(app, owner, "Private")
    client = logged_in_client(app, other)
    client.post("/notifications/%d/read" % notification_id)
    assert fetch(app, Notification, notification_id).is_read is False
    assert b"Private" not in client.get("/notifications/").data


def test_notification_links_lead_to_destination(app):
    donor = create_user(app, "donor")
    recipient = create_user(app, "recipient")
    contact_id = create_contact(app, donor, recipient)
    make_notification(
        app, donor, "Linked", related_type="contact_request", related_id=contact_id
    )
    client = logged_in_client(app, donor)
    assert ("/contact/%d" % contact_id).encode() in client.get("/notifications/").data


def test_next_redirect_must_be_local(app):
    user_id = create_user(app, "recipient")
    notification_id = make_notification(app, user_id)
    client = logged_in_client(app, user_id)
    response = client.post(
        "/notifications/%d/read" % notification_id, data={"next": "https://evil.example"}
    )
    assert "evil.example" not in response.headers["Location"]
