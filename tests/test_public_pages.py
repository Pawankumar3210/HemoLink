"""Public pages render, and the landing page reports live (not invented) numbers."""

import pytest

from tests.helpers import create_blood_request, create_user, logged_in_client

PUBLIC = [
    "/",
    "/about",
    "/how-it-works",
    "/sdg-3",
    "/privacy",
    "/terms",
    "/login",
    "/register",
    "/register/donor",
    "/register/recipient",
    "/forgot-password",
]


@pytest.mark.parametrize("path", PUBLIC)
def test_public_page_renders(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert b"HemoLink" in response.data


def test_landing_page_content(client):
    page = client.get("/").data
    assert b"Every Drop Counts. Every Connection Matters." in page
    assert b"Connecting Donors. Saving Lives." in page
    assert b"Find Blood Donors" in page and b"Become a Donor" in page
    for group in (b"A+", b"A-", b"B+", b"B-", b"AB+", b"AB-", b"O+", b"O-"):
        assert group in page
    assert b"not a blood bank" in page.lower()


def test_landing_stats_are_live(app, client):
    empty = client.get("/").data
    assert b"<dd>0</dd>" in empty
    create_user(app, "donor")
    create_user(app, "donor")
    create_user(app, "donor", status="suspended")
    recipient = create_user(app, "recipient")
    create_blood_request(app, recipient)
    page = client.get("/").data
    assert b"<dt>Registered donors</dt><dd>2</dd>" in page
    assert b"<dt>Open blood requests</dt><dd>1</dd>" in page


def test_find_donors_link_requires_login_for_visitors(client):
    response = client.get("/donors/search")
    assert response.status_code == 302 and "/login" in response.headers["Location"]


def test_navigation_adapts_to_role(app):
    recipient = logged_in_client(app, create_user(app, "recipient"))
    donor = logged_in_client(app, create_user(app, "donor"))
    nav_link = b'<li><a href="/donors/search">Find donors</a></li>'
    assert nav_link in recipient.get("/").data
    assert nav_link not in donor.get("/").data
    assert b"Dashboard" in donor.get("/").data
