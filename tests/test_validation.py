"""Unit tests for server-side validation (no database needed)."""

from datetime import date, timedelta

import pytest

from app.services import validation as v


def test_email_normalised_and_validated():
    assert v.validate_email("  Asha@Example.COM ") == ("asha@example.com", None)
    for bad in ("", "no-at-sign", "a@b", "a@@b.com", "a b@c.com", "a..b@c.com"):
        assert v.validate_email(bad)[1]


@pytest.mark.parametrize(
    "raw,ok",
    [
        ("+91 98765-43210", True),
        ("(080) 2345 6789", True),
        ("12345", False),
        ("abcdefghij", False),
        ("", False),
        ("+1234567890123456", False),
    ],
)
def test_phone(raw, ok):
    assert (v.validate_phone(raw)[1] is None) is ok


@pytest.mark.parametrize(
    "password,ok",
    [
        ("Passw0rd!x", True),
        ("short1", False),
        ("allletters", False),
        ("12345678", False),
        ("password1", False),
        ("a" * 129 + "1", False),
    ],
)
def test_password_policy(password, ok):
    assert (v.validate_password(password) is None) is ok


def test_password_cannot_equal_email():
    assert v.validate_password("someone1@x.com", "someone1@x.com")


def test_full_name_rules():
    assert v.validate_full_name("Asha  K. O'Neil-Rao")[1] is None
    assert v.validate_full_name("A")[1]
    assert v.validate_full_name("<script>")[1]
    assert v.validate_full_name("1abc")[1]


def test_donor_fields_valid_and_normalised():
    cleaned, errors = v.validate_donor_fields(
        {
            "blood_group": "AB-",
            "age": "40",
            "state": "Karnataka",
            "city": "  bengaluru ",
            "last_donation_date": "2026-01-02",
            "availability_status": "available",
            "visible_in_search": "on",
        },
        today=date(2026, 11, 21),
    )
    assert errors == {}
    assert cleaned["city"] == "Bengaluru"
    assert cleaned["visible_in_search"] is True
    assert cleaned["share_last_donation_date"] is False
    assert cleaned["last_donation_date"] == date(2026, 1, 2)


@pytest.mark.parametrize(
    "field,value",
    [
        ("blood_group", "Z+"),
        ("age", "17"),
        ("age", "66"),
        ("age", "abc"),
        ("state", "Atlantis"),
        ("city", ""),
        ("last_donation_date", "2999-01-01"),
        ("last_donation_date", "not-a-date"),
        ("availability_status", "maybe"),
        ("gender", "robot"),
    ],
)
def test_donor_fields_reject_bad_values(field, value):
    form = {
        "blood_group": "O+",
        "age": "30",
        "state": "Karnataka",
        "city": "Bengaluru",
        "availability_status": "available",
    }
    form[field] = value
    _, errors = v.validate_donor_fields(form)
    assert field in errors


def test_blood_request_validation():
    today = date(2026, 11, 21)
    good = {
        "blood_group": "A+",
        "units_required": "3",
        "state": "Goa",
        "city": "Panaji",
        "required_by": "2026-11-25",
        "urgency": "urgent",
    }
    cleaned, errors = v.validate_blood_request(good, today=today)
    assert errors == {} and cleaned["units_required"] == 3
    for field, value in [
        ("units_required", "0"),
        ("units_required", "21"),
        ("required_by", "2026-11-20"),
        ("required_by", str(today + timedelta(days=400))),
        ("urgency", "whenever"),
        ("notes", "x" * 501),
        ("hospital_name", "h" * 151),
    ]:
        _, errors = v.validate_blood_request({**good, field: value}, today=today)
        assert field in errors, field


def test_contact_message_validation():
    assert v.validate_contact_message({"message": "short"})[1]
    cleaned, errors = v.validate_contact_message(
        {"message": "Please help us today", "blood_request_id": "7"}
    )
    assert errors == {} and cleaned["blood_request_id"] == 7
    assert v.validate_contact_message(
        {"message": "Please help us today", "blood_request_id": "x"}
    )[1]


def test_search_filters_reject_malformed_input():
    cleaned, errors = v.validate_search_filters(
        {"blood_group": "'; DROP TABLE users;--", "sort": "evil", "state": "x"}
    )
    assert set(errors) == {"blood_group", "sort", "state"}
    assert cleaned["blood_group"] == "" and cleaned["sort"] == "availability"


def test_clean_text_removes_control_characters_and_collapses_space():
    assert v.clean_text("  a \x00 b\t\tc ") == "a b c"
    assert v.clean_multiline("a\r\n\r\n b", 10) == "a\n\nb"


def test_registration_requires_terms_and_donor_fields():
    _, errors = v.validate_registration({}, "donor")
    assert {
        "full_name",
        "email",
        "phone",
        "password",
        "blood_group",
        "accept_terms",
    } <= set(errors)
    _, errors = v.validate_registration({}, "recipient")
    assert "blood_group" not in errors


def test_password_change_rules():
    _, errors = v.validate_password_change(
        {
            "current_password": "Old1password",
            "new_password": "Old1password",
            "confirm_password": "Old1password",
        }
    )
    assert "new_password" in errors
    _, errors = v.validate_password_change(
        {"current_password": "x", "new_password": "Newpass12", "confirm_password": "no"}
    )
    assert "confirm_password" in errors
