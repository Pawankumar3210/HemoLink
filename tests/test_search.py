"""Donor search: filters, privacy, pagination and malformed input."""

from datetime import date

from tests.helpers import (
    create_user,
    get_email,
    get_phone,
    logged_in_client,
    profile_id,
)


def names(response):
    return response.data.decode()


def card_count(response):
    return response.data.count(b'class="donor-card"')


def make_recipient_client(app):
    return logged_in_client(app, create_user(app, "recipient"))


def seed_donors(app):
    ids = {}
    ids["o_blr"] = create_user(app, "donor", name="Oscar Blr", blood_group="O+")
    ids["o_mys"] = create_user(app, "donor", name="Olive Mys", blood_group="O+", city="Mysuru")
    ids["a_blr"] = create_user(app, "donor", name="Amit Blr", blood_group="A-")
    ids["b_pune"] = create_user(
        app, "donor", name="Bela Pune", blood_group="B+", state="Maharashtra", city="Pune"
    )
    ids["o_temp"] = create_user(
        app, "donor", name="Omar Temp", blood_group="O+", availability="temporarily_unavailable"
    )
    return ids


def test_search_by_blood_group(app):
    seed_donors(app)
    client = make_recipient_client(app)
    response = client.get("/donors/search", query_string={"blood_group": "O+"})
    text = names(response)
    assert response.status_code == 200 and card_count(response) == 3
    assert "Oscar Blr" in text and "Olive Mys" in text and "Omar Temp" in text
    assert "Amit Blr" not in text and "Bela Pune" not in text


def test_search_by_state_and_city(app):
    seed_donors(app)
    client = make_recipient_client(app)
    by_state = client.get("/donors/search", query_string={"state": "Maharashtra"})
    assert card_count(by_state) == 1 and "Bela Pune" in names(by_state)
    by_city = client.get("/donors/search", query_string={"city": "mys"})
    assert card_count(by_city) == 1 and "Olive Mys" in names(by_city)


def test_search_by_availability(app):
    seed_donors(app)
    client = make_recipient_client(app)
    response = client.get(
        "/donors/search", query_string={"availability": "temporarily_unavailable"}
    )
    assert card_count(response) == 1 and "Omar Temp" in names(response)


def test_search_by_name(app):
    seed_donors(app)
    client = make_recipient_client(app)
    response = client.get("/donors/search", query_string={"q": "amit"})
    assert card_count(response) == 1 and "Amit Blr" in names(response)


def test_combined_filters(app):
    seed_donors(app)
    client = make_recipient_client(app)
    response = client.get(
        "/donors/search",
        query_string={
            "blood_group": "O+",
            "state": "Karnataka",
            "city": "Bengaluru",
            "availability": "available",
        },
    )
    assert card_count(response) == 1 and "Oscar Blr" in names(response)


def test_empty_results_show_empty_state(app):
    seed_donors(app)
    client = make_recipient_client(app)
    response = client.get("/donors/search", query_string={"blood_group": "AB-"})
    assert response.status_code == 200 and card_count(response) == 0
    assert b"No donors match these filters" in response.data


def test_like_wildcards_in_city_are_literal(app):
    seed_donors(app)
    client = make_recipient_client(app)
    response = client.get("/donors/search", query_string={"city": "%"})
    assert response.status_code == 200 and card_count(response) == 0


def test_hidden_donors_never_appear(app):
    create_user(app, "donor", name="Visible Vera", blood_group="O+")
    create_user(app, "donor", name="Hidden Hana", blood_group="O+", visible=False)
    client = make_recipient_client(app)
    response = client.get("/donors/search", query_string={"blood_group": "O+"})
    assert "Visible Vera" in names(response) and "Hidden Hana" not in names(response)


def test_hidden_donor_with_available_status_is_still_hidden(app):
    create_user(app, "donor", name="Hidden Hana", visible=False, availability="available")
    client = make_recipient_client(app)
    assert b"Hidden Hana" not in client.get("/donors/search").data


def test_suspended_and_deleted_donors_excluded(app):
    create_user(app, "donor", name="Suspended Sam", status="suspended")
    create_user(app, "donor", name="Deleted Dan", status="deleted")
    create_user(app, "donor", name="Active Anu")
    client = make_recipient_client(app)
    text = names(client.get("/donors/search"))
    assert "Active Anu" in text
    assert "Suspended Sam" not in text and "Deleted Dan" not in text


def test_results_never_expose_contact_details(app):
    donor = create_user(app, "donor", name="Private Pia")
    client = make_recipient_client(app)
    response = client.get("/donors/search")
    assert "Private Pia" in names(response)
    assert get_phone(app, donor).encode() not in response.data
    assert get_email(app, donor).encode() not in response.data
    detail = client.get("/donors/%d" % profile_id(app, donor))
    assert detail.status_code == 200
    assert get_phone(app, donor).encode() not in detail.data
    assert get_email(app, donor).encode() not in detail.data


def test_last_donation_date_only_shown_when_shared(app):
    create_user(
        app, "donor", name="Sharing Sia", last_donation_date=date(2026, 3, 4), share_date=True
    )
    create_user(
        app, "donor", name="Secret Sid", last_donation_date=date(2026, 5, 6), share_date=False
    )
    client = make_recipient_client(app)
    text = names(client.get("/donors/search"))
    assert "04 Mar 2026" in text
    assert "06 May 2026" not in text


def test_pagination(app):
    for i in range(12):
        create_user(app, "donor", name="Donor Number%02d" % i)
    client = make_recipient_client(app)
    first = client.get("/donors/search")
    second = client.get("/donors/search", query_string={"page": 2})
    assert card_count(first) == 9 and card_count(second) == 3
    assert b'class="pagination"' in first.data
    beyond = client.get("/donors/search", query_string={"page": 99})
    assert beyond.status_code == 200 and card_count(beyond) == 0
    junk = client.get("/donors/search", query_string={"page": "abc"})
    assert junk.status_code == 200 and card_count(junk) == 9


def test_pagination_links_keep_filters(app):
    for i in range(12):
        create_user(app, "donor", blood_group="O+", name="Donor Number%02d" % i)
    client = make_recipient_client(app)
    response = client.get("/donors/search", query_string={"blood_group": "O+"})
    assert b"blood_group=O%2B" in response.data and b"page=2" in response.data


def test_sorting(app):
    create_user(app, "donor", name="Zed Unavailable", availability="unavailable")
    create_user(app, "donor", name="Mia Available")
    create_user(app, "donor", name="Abe Temp", availability="temporarily_unavailable")
    client = make_recipient_client(app)
    default = names(client.get("/donors/search"))
    assert default.index("Mia Available") < default.index("Abe Temp")
    assert default.index("Abe Temp") < default.index("Zed Unavailable")
    by_name = names(client.get("/donors/search", query_string={"sort": "name"}))
    assert by_name.index("Abe Temp") < by_name.index("Mia Available")


def test_malformed_input_is_rejected_safely(app):
    seed_donors(app)
    client = make_recipient_client(app)
    for params in (
        {"blood_group": "'; DROP TABLE users;--"},
        {"sort": "evil"},
        {"state": "Atlantis"},
        {"availability": "maybe"},
        {"city": "x" * 500},
    ):
        response = client.get("/donors/search", query_string=params)
        assert response.status_code == 400, params
    assert client.get("/donors/search").status_code == 200  # table still exists


def test_search_requires_recipient_role_and_login(app, client):
    assert client.get("/donors/search").status_code == 302
    donor_client = logged_in_client(app, create_user(app, "donor"))
    assert donor_client.get("/donors/search").status_code == 403


def test_unknown_or_hidden_profile_detail_is_404(app):
    hidden = create_user(app, "donor", visible=False)
    client = make_recipient_client(app)
    assert client.get("/donors/%d" % profile_id(app, hidden)).status_code == 404
    assert client.get("/donors/99999").status_code == 404
