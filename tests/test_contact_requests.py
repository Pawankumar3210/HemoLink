"""The consent-based contact workflow."""

from datetime import timedelta

from sqlalchemy import select

from app.extensions import db
from app.models import ContactRequest, User
from app.utils.time import utcnow
from tests.helpers import (
    count,
    create_blood_request,
    create_contact,
    create_user,
    fetch,
    get_phone,
    logged_in_client,
    notifications_for,
    profile_id,
)

MESSAGE = {"message": "We urgently need O+ blood at City Hospital."}


def setup_pair(app, **donor_kwargs):
    donor = create_user(app, "donor", name="Dana Donor", **donor_kwargs)
    recipient = create_user(app, "recipient", name="Ravi Recipient")
    return donor, recipient


def send_request(app, recipient, donor, **extra):
    client = logged_in_client(app, recipient)
    response = client.post(
        "/contact/request/%d" % profile_id(app, donor), data={**MESSAGE, **extra}
    )
    return client, response


def only_contact(app):
    with app.app_context():
        row = db.session.scalar(select(ContactRequest))
        db.session.expunge(row)
        return row


def test_recipient_can_create_contact_request(app):
    donor, recipient = setup_pair(app)
    _, response = send_request(app, recipient, donor)
    assert response.status_code == 302
    contact = only_contact(app)
    assert contact.status == "pending"
    assert contact.donor_id == donor and contact.recipient_id == recipient
    assert contact.donor_consent_at is None
    assert any(n.title == "New contact request" for n in notifications_for(app, donor))


def test_invalid_contact_message_rejected(app):
    donor, recipient = setup_pair(app)
    client = logged_in_client(app, recipient)
    response = client.post(
        "/contact/request/%d" % profile_id(app, donor), data={"message": "hi"}
    )
    assert response.status_code == 400
    assert count(app, ContactRequest) == 0


def test_phone_hidden_until_donor_accepts(app):
    donor, recipient = setup_pair(app)
    recipient_client, _ = send_request(app, recipient, donor)
    contact_id = only_contact(app).id
    phone = get_phone(app, donor).encode()
    page = recipient_client.get("/contact/%d" % contact_id)
    assert page.status_code == 200 and phone not in page.data
    assert phone not in recipient_client.get("/contact/tracking").data
    assert phone not in recipient_client.get("/donors/%d" % profile_id(app, donor)).data


def test_donor_accepts_and_recipient_sees_phone(app):
    donor, recipient = setup_pair(app)
    recipient_client, _ = send_request(app, recipient, donor)
    contact_id = only_contact(app).id
    donor_client = logged_in_client(app, donor)
    response = donor_client.post("/contact/%d/accept" % contact_id)
    assert response.status_code == 302
    contact = fetch(app, ContactRequest, contact_id)
    assert contact.status == "accepted"
    assert contact.donor_consent_at is not None and contact.responded_at is not None
    page = recipient_client.get("/contact/%d" % contact_id)
    assert get_phone(app, donor).encode() in page.data
    assert any(
        n.title == "Contact request accepted" for n in notifications_for(app, recipient)
    )
    # the donor also sees the recipient's number once they have accepted
    assert (
        get_phone(app, recipient).encode()
        in donor_client.get("/contact/%d" % contact_id).data
    )


def test_donor_declines_and_details_stay_hidden(app):
    donor, recipient = setup_pair(app)
    recipient_client, _ = send_request(app, recipient, donor)
    contact_id = only_contact(app).id
    donor_client = logged_in_client(app, donor)
    assert donor_client.post("/contact/%d/decline" % contact_id).status_code == 302
    contact = fetch(app, ContactRequest, contact_id)
    assert contact.status == "declined" and contact.donor_consent_at is None
    page = recipient_client.get("/contact/%d" % contact_id)
    assert get_phone(app, donor).encode() not in page.data
    assert b"declined" in page.data
    assert any(
        n.title == "Contact request declined" for n in notifications_for(app, recipient)
    )


def test_request_cannot_be_accepted_twice_or_after_decline(app):
    donor, recipient = setup_pair(app)
    send_request(app, recipient, donor)
    contact_id = only_contact(app).id
    donor_client = logged_in_client(app, donor)
    donor_client.post("/contact/%d/accept" % contact_id)
    first = fetch(app, ContactRequest, contact_id)
    again = donor_client.post("/contact/%d/accept" % contact_id, follow_redirects=True)
    assert b"can no longer be changed" in again.data
    donor_client.post("/contact/%d/decline" % contact_id)
    second = fetch(app, ContactRequest, contact_id)
    assert second.status == "accepted"
    assert second.donor_consent_at == first.donor_consent_at
    accepted_notices = [
        n
        for n in notifications_for(app, recipient)
        if n.title == "Contact request accepted"
    ]
    assert len(accepted_notices) == 1


def test_other_donor_cannot_respond(app):
    donor, recipient = setup_pair(app)
    send_request(app, recipient, donor)
    contact_id = only_contact(app).id
    intruder = logged_in_client(app, create_user(app, "donor"))
    assert intruder.post("/contact/%d/accept" % contact_id).status_code == 404
    assert intruder.post("/contact/%d/decline" % contact_id).status_code == 404
    assert fetch(app, ContactRequest, contact_id).status == "pending"


def test_recipient_cannot_approve_own_request(app):
    donor, recipient = setup_pair(app)
    recipient_client, _ = send_request(app, recipient, donor)
    contact_id = only_contact(app).id
    assert recipient_client.post("/contact/%d/accept" % contact_id).status_code == 403
    assert fetch(app, ContactRequest, contact_id).status == "pending"


def test_duplicate_active_request_blocked(app):
    donor, recipient = setup_pair(app)
    client, _ = send_request(app, recipient, donor)
    second = client.post("/contact/request/%d" % profile_id(app, donor), data=MESSAGE)
    assert second.status_code == 400
    assert b"already have an active contact request" in second.data
    assert count(app, ContactRequest) == 1


def test_duplicate_blocked_while_accepted_but_allowed_after_revoke(app):
    donor, recipient = setup_pair(app)
    client, _ = send_request(app, recipient, donor)
    contact_id = only_contact(app).id
    donor_client = logged_in_client(app, donor)
    donor_client.post("/contact/%d/accept" % contact_id)
    blocked = client.post("/contact/request/%d" % profile_id(app, donor), data=MESSAGE)
    assert blocked.status_code == 400
    donor_client.post("/contact/%d/revoke" % contact_id)
    allowed = client.post("/contact/request/%d" % profile_id(app, donor), data=MESSAGE)
    assert allowed.status_code == 302
    assert count(app, ContactRequest) == 2


def test_different_purposes_are_not_duplicates(app):
    donor, recipient = setup_pair(app)
    client, _ = send_request(app, recipient, donor)
    request_id = create_blood_request(app, recipient)
    linked = client.post(
        "/contact/request/%d" % profile_id(app, donor),
        data={**MESSAGE, "blood_request_id": str(request_id)},
    )
    assert linked.status_code == 302
    assert count(app, ContactRequest) == 2


def test_cannot_link_someone_elses_blood_request(app):
    donor, recipient = setup_pair(app)
    other = create_user(app, "recipient")
    foreign = create_blood_request(app, other)
    client = logged_in_client(app, recipient)
    response = client.post(
        "/contact/request/%d" % profile_id(app, donor),
        data={**MESSAGE, "blood_request_id": str(foreign)},
    )
    assert response.status_code == 400 and count(app, ContactRequest) == 0


def test_recently_declined_request_cannot_be_repeated_immediately(app):
    donor, recipient = setup_pair(app)
    create_contact(
        app,
        donor,
        recipient,
        status="declined",
        responded_at=utcnow() - timedelta(days=1),
    )
    client = logged_in_client(app, recipient)
    response = client.post("/contact/request/%d" % profile_id(app, donor), data=MESSAGE)
    assert (
        response.status_code == 400 and b"declined a similar request" in response.data
    )
    old = create_user(app, "donor")
    create_contact(
        app,
        old,
        recipient,
        status="declined",
        responded_at=utcnow() - timedelta(days=30),
    )
    ok = client.post("/contact/request/%d" % profile_id(app, old), data=MESSAGE)
    assert ok.status_code == 302


def test_unavailable_donor_cannot_be_contacted(app):
    donor, recipient = setup_pair(app, availability="unavailable")
    client = logged_in_client(app, recipient)
    response = client.post("/contact/request/%d" % profile_id(app, donor), data=MESSAGE)
    assert response.status_code == 400 and count(app, ContactRequest) == 0


def test_revoking_consent_hides_phone_again(app):
    donor, recipient = setup_pair(app)
    recipient_client, _ = send_request(app, recipient, donor)
    contact_id = only_contact(app).id
    donor_client = logged_in_client(app, donor)
    donor_client.post("/contact/%d/accept" % contact_id)
    assert (
        get_phone(app, donor).encode()
        in recipient_client.get("/contact/%d" % contact_id).data
    )
    assert donor_client.post("/contact/%d/revoke" % contact_id).status_code == 302
    contact = fetch(app, ContactRequest, contact_id)
    assert contact.recipient_access_revoked_at is not None
    assert (
        get_phone(app, donor).encode()
        not in recipient_client.get("/contact/%d" % contact_id).data
    )
    assert (
        get_phone(app, recipient).encode()
        not in donor_client.get("/contact/%d" % contact_id).data
    )


def test_suspended_donor_phone_is_not_disclosed(app):
    donor, recipient = setup_pair(app)
    recipient_client, _ = send_request(app, recipient, donor)
    contact_id = only_contact(app).id
    logged_in_client(app, donor).post("/contact/%d/accept" % contact_id)
    with app.app_context():
        db.session.get(User, donor).account_status = "suspended"
        db.session.commit()
    page = recipient_client.get("/contact/%d" % contact_id)
    assert get_phone(app, donor).encode() not in page.data


def test_recipient_can_withdraw_pending_request(app):
    donor, recipient = setup_pair(app)
    recipient_client, _ = send_request(app, recipient, donor)
    contact_id = only_contact(app).id
    assert recipient_client.post("/contact/%d/withdraw" % contact_id).status_code == 302
    assert fetch(app, ContactRequest, contact_id).status == "withdrawn"
    donor_client = logged_in_client(app, donor)
    again = donor_client.post("/contact/%d/accept" % contact_id, follow_redirects=True)
    assert b"can no longer be changed" in again.data
    assert fetch(app, ContactRequest, contact_id).status == "withdrawn"


def test_only_requesting_recipient_can_withdraw(app):
    donor, recipient = setup_pair(app)
    send_request(app, recipient, donor)
    contact_id = only_contact(app).id
    other = logged_in_client(app, create_user(app, "recipient"))
    assert other.post("/contact/%d/withdraw" % contact_id).status_code == 404
    assert fetch(app, ContactRequest, contact_id).status == "pending"


def test_listing_pages_for_both_sides(app):
    donor, recipient = setup_pair(app)
    send_request(app, recipient, donor)
    donor_client = logged_in_client(app, donor)
    assert b"Ravi Recipient" in donor_client.get("/contact/incoming").data
    assert b"Ravi Recipient" not in donor_client.get("/contact/history").data
    contact_id = only_contact(app).id
    donor_client.post("/contact/%d/decline" % contact_id)
    assert b"Ravi Recipient" in donor_client.get("/contact/history").data
    recipient_client = logged_in_client(app, recipient)
    assert b"Dana Donor" in recipient_client.get("/contact/tracking").data
