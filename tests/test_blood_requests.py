"""Blood request creation, validation, ownership and status changes."""

from datetime import date, timedelta

from sqlalchemy import select

from app.extensions import db
from app.models import BloodRequest, ContactRequest, Notification
from tests.helpers import (
    count,
    create_blood_request,
    create_contact,
    create_user,
    fetch,
    logged_in_client,
    notifications_for,
    request_form,
)


def test_create_request(app):
    user_id = create_user(app, "recipient")
    client = logged_in_client(app, user_id)
    response = client.post("/requests/new", data=request_form())
    assert response.status_code == 302
    with app.app_context():
        row = db.session.scalar(select(BloodRequest))
        assert row.requester_id == user_id and row.status == "open"
        assert row.blood_group == "A+" and row.units_required == 2
        assert row.city == "Mysuru" and row.urgency == "high"
    detail = client.get(response.headers["Location"])
    assert detail.status_code == 200 and b"City Hospital" in detail.data


def test_invalid_request_rejected(app):
    client = logged_in_client(app, create_user(app, "recipient"))
    for override in (
        {"blood_group": "Q+"},
        {"units_required": "0"},
        {"units_required": "abc"},
        {"required_by": (date.today() - timedelta(days=1)).isoformat()},
        {"urgency": "asap"},
        {"city": ""},
        {"state": "Nowhere"},
        {"notes": "n" * 501},
    ):
        response = client.post("/requests/new", data=request_form(**override))
        assert response.status_code == 400, override
    assert count(app, BloodRequest) == 0


def test_user_generated_text_is_escaped(app):
    client = logged_in_client(app, create_user(app, "recipient"))
    response = client.post(
        "/requests/new",
        data=request_form(notes="<script>alert(1)</script>", hospital_name="<b>H</b>"),
    )
    page = client.get(response.headers["Location"]).data
    assert b"<script>alert(1)</script>" not in page
    assert b"&lt;script&gt;" in page and b"&lt;b&gt;H&lt;/b&gt;" in page


def test_edit_open_request(app):
    user_id = create_user(app, "recipient")
    request_id = create_blood_request(app, user_id, units_required=1)
    client = logged_in_client(app, user_id)
    assert client.get("/requests/%d/edit" % request_id).status_code == 200
    response = client.post(
        "/requests/%d/edit" % request_id, data=request_form(units_required="5")
    )
    assert response.status_code == 302
    row = fetch(app, BloodRequest, request_id)
    assert row.units_required == 5 and row.blood_group == "A+"


def test_cannot_edit_closed_request(app):
    user_id = create_user(app, "recipient")
    request_id = create_blood_request(app, user_id, status="fulfilled")
    client = logged_in_client(app, user_id)
    response = client.post("/requests/%d/edit" % request_id, data=request_form())
    assert response.status_code == 302
    assert fetch(app, BloodRequest, request_id).units_required == 2


def test_cancel_and_fulfil(app):
    user_id = create_user(app, "recipient")
    to_cancel = create_blood_request(app, user_id)
    to_fulfil = create_blood_request(app, user_id)
    client = logged_in_client(app, user_id)
    assert client.post("/requests/%d/cancel" % to_cancel).status_code == 302
    assert client.post("/requests/%d/fulfill" % to_fulfil).status_code == 302
    cancelled = fetch(app, BloodRequest, to_cancel)
    fulfilled = fetch(app, BloodRequest, to_fulfil)
    assert cancelled.status == "cancelled" and cancelled.status_changed_at is not None
    assert fulfilled.status == "fulfilled"
    titles = {n.title for n in notifications_for(app, user_id)}
    assert {"Blood request cancelled", "Blood request fulfilled"} <= titles


def test_closed_request_cannot_change_again(app):
    user_id = create_user(app, "recipient")
    request_id = create_blood_request(app, user_id, status="cancelled")
    client = logged_in_client(app, user_id)
    response = client.post("/requests/%d/fulfill" % request_id, follow_redirects=True)
    assert b"cannot be changed" in response.data
    assert fetch(app, BloodRequest, request_id).status == "cancelled"


def test_cancelling_notifies_donors_with_linked_contacts(app):
    recipient = create_user(app, "recipient")
    donor = create_user(app, "donor")
    request_id = create_blood_request(app, recipient)
    create_contact(app, donor, recipient, blood_request_id=request_id)
    client = logged_in_client(app, recipient)
    client.post("/requests/%d/cancel" % request_id)
    assert any(
        n.title == "A linked blood request was closed"
        for n in notifications_for(app, donor)
    )


def test_list_filters_by_status_and_paginates(app):
    user_id = create_user(app, "recipient")
    for _ in range(17):
        create_blood_request(app, user_id)
    create_blood_request(app, user_id, status="fulfilled")
    client = logged_in_client(app, user_id)
    assert client.get("/requests/").status_code == 200
    page2 = client.get("/requests/", query_string={"page": 2})
    assert page2.status_code == 200
    fulfilled = client.get("/requests/", query_string={"status": "fulfilled"})
    assert fulfilled.data.count(b"Fulfilled") >= 1
    assert client.get("/requests/", query_string={"status": "bogus"}).status_code == 200


def test_requests_list_only_shows_own(app):
    mine = create_user(app, "recipient")
    other = create_user(app, "recipient")
    create_blood_request(app, other, hospital_name="Other Hospital", city="Chennai", state="Tamil Nadu")
    create_blood_request(app, mine, city="Mysuru")
    client = logged_in_client(app, mine)
    text = client.get("/requests/").data
    assert b"Mysuru" in text and b"Chennai" not in text


def test_donor_open_requests_listing_and_defaults(app):
    recipient = create_user(app, "recipient")
    create_blood_request(app, recipient, blood_group="O+", city="Bengaluru")
    create_blood_request(app, recipient, blood_group="AB-", city="Kochi", state="Kerala")
    create_blood_request(app, recipient, blood_group="O+", status="cancelled", city="Hidden")
    donor = logged_in_client(app, create_user(app, "donor", blood_group="O+"))
    default = donor.get("/donor/blood-requests")
    assert b"Bengaluru" in default.data
    assert b"Kochi" not in default.data and b"Hidden" not in default.data
    widened = donor.get("/donor/blood-requests", query_string={"blood_group": "", "state": ""})
    assert b"Kochi" in widened.data and b"Hidden" not in widened.data


def test_request_deleted_user_requests_cancelled(app):
    from tests.helpers import PASSWORD

    recipient = create_user(app, "recipient")
    request_id = create_blood_request(app, recipient)
    client = logged_in_client(app, recipient)
    client.post("/account/delete", data={"password": PASSWORD, "confirm_delete": "on"})
    assert fetch(app, BloodRequest, request_id).status == "cancelled"
    assert count(app, Notification, Notification.user_id == recipient) == 0
    assert count(app, ContactRequest) == 0
