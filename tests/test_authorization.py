"""Role-based access control and object-level authorization."""

import pytest

from app.models import BloodRequest, ContactRequest, DonorProfile
from tests.helpers import (
    count,
    create_blood_request,
    create_contact,
    create_user,
    fetch,
    logged_in_client,
    profile_id,
)

DONOR_ONLY = [
    "/dashboard/donor",
    "/donor/profile",
    "/donor/availability",
    "/contact/incoming",
]
RECIPIENT_ONLY = [
    "/dashboard/recipient",
    "/donors/search",
    "/requests/",
    "/requests/new",
    "/contact/tracking",
]
ADMIN_ONLY = [
    "/admin/",
    "/admin/users",
    "/admin/donors",
    "/admin/requests",
    "/admin/contacts",
    "/admin/audit",
    "/admin/notices",
    "/admin/system",
]


@pytest.mark.parametrize("path", RECIPIENT_ONLY)
def test_donor_cannot_access_recipient_pages(app, path):
    client = logged_in_client(app, create_user(app, "donor"))
    response = client.get(path)
    if path == "/donors/search":
        assert response.status_code == 302
        assert "/donor/blood-requests" in response.headers["Location"]
    else:
        assert response.status_code == 403


@pytest.mark.parametrize("path", DONOR_ONLY)
def test_recipient_cannot_access_donor_pages(app, path):
    client = logged_in_client(app, create_user(app, "recipient"))
    assert client.get(path).status_code == 403


@pytest.mark.parametrize("path", ADMIN_ONLY)
def test_non_admins_cannot_access_admin_pages(app, path):
    for role in ("donor", "recipient"):
        client = logged_in_client(app, create_user(app, role))
        assert client.get(path).status_code == 403, (role, path)


@pytest.mark.parametrize("path", ADMIN_ONLY)
def test_admin_pages_work_for_admin(app, path):
    client = logged_in_client(app, create_user(app, "admin"))
    assert client.get(path).status_code == 200, path


def test_admin_post_endpoints_forbidden_for_non_admin(app):
    victim = create_user(app, "donor")
    request_id = create_blood_request(app, create_user(app, "recipient"))
    client = logged_in_client(app, create_user(app, "recipient"))
    assert client.post("/admin/users/%d/suspend" % victim).status_code == 403
    assert client.post("/admin/users/%d/reactivate" % victim).status_code == 403
    response = client.post(
        "/admin/requests/%d/status" % request_id,
        data={"status": "rejected", "reason": "x"},
    )
    assert response.status_code == 403
    assert fetch(app, BloodRequest, request_id).status == "open"


def test_role_cannot_be_escalated_via_request_data(app):
    user_id = create_user(app, "recipient")
    client = logged_in_client(app, user_id)
    client.post(
        "/account/profile",
        data={"full_name": "Sneaky User", "phone": "+919876543210", "role": "admin"},
    )
    assert client.get("/admin/").status_code == 403


def test_recipient_cannot_view_or_change_another_recipients_request(app):
    owner = create_user(app, "recipient")
    intruder = logged_in_client(app, create_user(app, "recipient"))
    request_id = create_blood_request(app, owner)
    assert intruder.get("/requests/%d" % request_id).status_code == 404
    assert intruder.get("/requests/%d/edit" % request_id).status_code == 404
    assert intruder.post("/requests/%d/cancel" % request_id).status_code == 404
    assert intruder.post("/requests/%d/fulfill" % request_id).status_code == 404
    assert fetch(app, BloodRequest, request_id).status == "open"


def test_donor_cannot_modify_a_blood_request(app):
    owner = create_user(app, "recipient")
    donor = logged_in_client(app, create_user(app, "donor"))
    request_id = create_blood_request(app, owner)
    assert donor.get("/requests/%d" % request_id).status_code == 200
    assert donor.get("/requests/%d/edit" % request_id).status_code == 403
    assert donor.post("/requests/%d/cancel" % request_id).status_code == 403
    assert fetch(app, BloodRequest, request_id).status == "open"


def test_donor_cannot_see_closed_requests(app):
    owner = create_user(app, "recipient")
    donor = logged_in_client(app, create_user(app, "donor"))
    request_id = create_blood_request(app, owner, status="cancelled")
    assert donor.get("/requests/%d" % request_id).status_code == 404


def test_users_cannot_open_other_peoples_contact_requests(app):
    donor = create_user(app, "donor")
    recipient = create_user(app, "recipient")
    contact_id = create_contact(app, donor, recipient)
    for outsider_role in ("donor", "recipient"):
        client = logged_in_client(app, create_user(app, outsider_role))
        assert client.get("/contact/%d" % contact_id).status_code == 404


def test_donor_cannot_edit_another_donors_profile_via_form(app):
    first = create_user(app, "donor", city="Mysuru")
    second_id = create_user(app, "donor", city="Pune", state="Maharashtra")
    client = logged_in_client(app, first)
    client.post(
        "/donor/profile/edit",
        data={
            "user_id": second_id,
            "blood_group": "A+",
            "age": "33",
            "state": "Karnataka",
            "city": "Hubballi",
            "availability_status": "available",
        },
    )
    assert fetch(app, DonorProfile, profile_id(app, second_id)).city == "Pune"
    assert fetch(app, DonorProfile, profile_id(app, first)).city == "Hubballi"


def test_contact_request_for_hidden_donor_is_404(app):
    donor = create_user(app, "donor", visible=False)
    client = logged_in_client(app, create_user(app, "recipient"))
    pid = profile_id(app, donor)
    assert client.get("/contact/request/%d" % pid).status_code == 404
    response = client.post(
        "/contact/request/%d" % pid, data={"message": "Please help us today"}
    )
    assert response.status_code == 404
    assert count(app, ContactRequest) == 0
