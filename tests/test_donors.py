"""Donor profile management, availability and privacy."""

from datetime import date

from app.models import DonorProfile
from tests.helpers import (
    create_user,
    fetch,
    get_phone,
    logged_in_client,
    profile_id,
)


def edit_data(**overrides):
    data = {
        "blood_group": "B+",
        "age": "35",
        "gender": "Female",
        "state": "Karnataka",
        "city": "mysuru",
        "last_donation_date": "2026-01-15",
        "availability_status": "temporarily_unavailable",
        "visible_in_search": "on",
        "share_last_donation_date": "on",
    }
    data.update(overrides)
    return data


def test_donor_can_update_profile(app):
    user_id = create_user(app, "donor", visible=False)
    client = logged_in_client(app, user_id)
    response = client.post("/donor/profile/edit", data=edit_data())
    assert response.status_code == 302
    profile = fetch(app, DonorProfile, profile_id(app, user_id))
    assert profile.blood_group == "B+" and profile.age == 35
    assert profile.city == "Mysuru"  # normalised
    assert profile.availability_status == "temporarily_unavailable"
    assert profile.visible_in_search is True
    assert profile.share_last_donation_date is True
    assert profile.last_donation_date == date(2026, 1, 15)


def test_invalid_profile_update_rejected_and_not_saved(app):
    user_id = create_user(app, "donor", blood_group="O+")
    client = logged_in_client(app, user_id)
    response = client.post(
        "/donor/profile/edit", data=edit_data(blood_group="Z+", age="12")
    )
    assert response.status_code == 400
    assert b"Select a blood group" in response.data
    profile = fetch(app, DonorProfile, profile_id(app, user_id))
    assert profile.blood_group == "O+" and profile.age == 30


def test_edit_form_prefills_current_values(app):
    client = logged_in_client(app, create_user(app, "donor", city="Mysuru"))
    response = client.get("/donor/profile/edit")
    assert response.status_code == 200 and b'value="Mysuru"' in response.data


def test_availability_page_updates_status_and_visibility(app):
    user_id = create_user(app, "donor", visible=True)
    client = logged_in_client(app, user_id)
    response = client.post(
        "/donor/availability", data={"availability_status": "unavailable"}
    )
    assert response.status_code == 302
    profile = fetch(app, DonorProfile, profile_id(app, user_id))
    assert profile.availability_status == "unavailable"
    assert profile.visible_in_search is False  # checkbox left unticked


def test_invalid_availability_rejected(app):
    user_id = create_user(app, "donor")
    client = logged_in_client(app, user_id)
    response = client.post("/donor/availability", data={"availability_status": "nope"})
    assert response.status_code == 400
    assert fetch(app, DonorProfile, profile_id(app, user_id)).availability_status == (
        "available"
    )


def test_quick_availability_keeps_visibility(app):
    user_id = create_user(app, "donor", visible=True)
    client = logged_in_client(app, user_id)
    response = client.post(
        "/donor/availability/quick",
        data={"availability_status": "temporarily_unavailable"},
    )
    assert response.status_code == 302
    profile = fetch(app, DonorProfile, profile_id(app, user_id))
    assert profile.availability_status == "temporarily_unavailable"
    assert profile.visible_in_search is True


def test_donor_pages_render(app):
    client = logged_in_client(app, create_user(app, "donor"))
    for path in (
        "/dashboard/donor",
        "/donor/profile",
        "/donor/profile/edit",
        "/donor/availability",
        "/donor/blood-requests",
        "/contact/incoming",
        "/contact/history",
        "/notifications/",
        "/account",
    ):
        assert client.get(path).status_code == 200, path


def test_profile_page_never_claims_phone_is_public(app):
    user_id = create_user(app, "donor")
    client = logged_in_client(app, user_id)
    response = client.get("/donor/profile")
    assert b"Only after you accept a contact request" in response.data
    assert get_phone(app, user_id).encode() in response.data  # donor sees their own


def test_account_update_and_password_change(app):
    from tests.helpers import PASSWORD, get_email

    user_id = create_user(app, "donor")
    client = logged_in_client(app, user_id)
    response = client.post(
        "/account/profile", data={"full_name": "Renamed Donor", "phone": "+919000011111"}
    )
    assert response.status_code == 302
    assert b"Renamed Donor" in client.get("/account").data

    bad = client.post(
        "/account/password",
        data={
            "current_password": "wrong-pass1",
            "new_password": "Newer1password",
            "confirm_password": "Newer1password",
        },
    )
    assert bad.status_code == 400 and b"incorrect" in bad.data

    good = client.post(
        "/account/password",
        data={
            "current_password": PASSWORD,
            "new_password": "Newer1password",
            "confirm_password": "Newer1password",
        },
    )
    assert good.status_code == 302
    fresh = app.test_client().post(
        "/login", data={"email": get_email(app, user_id), "password": "Newer1password"}
    )
    assert fresh.status_code == 302


def test_account_deletion_anonymises_and_hides_donor(app):
    from app.models import User
    from tests.helpers import PASSWORD

    user_id = create_user(app, "donor", name="Delete Me", email="delete.me@example.com")
    client = logged_in_client(app, user_id)
    no_confirm = client.post("/account/delete", data={"password": PASSWORD})
    assert no_confirm.status_code == 400
    wrong = client.post(
        "/account/delete", data={"password": "wrong-pass1", "confirm_delete": "on"}
    )
    assert wrong.status_code == 400
    ok = client.post(
        "/account/delete", data={"password": PASSWORD, "confirm_delete": "on"}
    )
    assert ok.status_code == 302
    user = fetch(app, User, user_id)
    assert user.account_status == "deleted"
    assert user.full_name == "Deleted user" and user.phone is None
    assert "delete.me" not in user.email
    assert client.get("/dashboard/donor").status_code == 302  # signed out
    from tests.helpers import count

    assert count(app, DonorProfile) == 0


def test_admin_cannot_self_delete(app):
    from tests.helpers import PASSWORD

    client = logged_in_client(app, create_user(app, "admin"))
    response = client.get("/account")
    assert b"Delete your account" not in response.data
    response = client.post(
        "/account/delete", data={"password": PASSWORD, "confirm_delete": "on"}
    )
    assert response.status_code == 400
