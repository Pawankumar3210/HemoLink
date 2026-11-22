"""Server-side input validation.

Every validator takes a mapping (``request.form`` / ``request.args``) and
returns ``(cleaned, errors)``. ``errors`` maps field names to a message; an
empty ``errors`` dict means the input is valid. Nothing here touches the
database, so it is easy to unit test.
"""

import re
import string
from datetime import date, datetime, timedelta

from app.constants import (
    AVAILABILITY_STATUSES,
    BLOOD_GROUPS,
    GENDERS,
    INDIAN_STATES,
    MAX_DONOR_AGE,
    MAX_UNITS_PER_REQUEST,
    MIN_DONOR_AGE,
    URGENCY_LEVELS,
)

EMAIL_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$"
)
PHONE_RE = re.compile(r"^\+?[0-9]{10,15}$")
PLACE_EXTRA = set(" .'-&()")
NAME_EXTRA = set(" .'-")
COMMON_PASSWORDS = {
    "password",
    "password1",
    "password123",
    "12345678",
    "123456789",
    "1234567890",
    "qwerty123",
    "qwertyuiop",
    "iloveyou1",
    "admin123",
    "welcome123",
    "letmein123",
}
SORT_OPTIONS = ("availability", "name", "newest")


def clean_text(value, max_length=None):
    """Strip, collapse internal whitespace and drop control characters."""
    if value is None:
        return ""
    text = str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")
    text = "".join(ch for ch in text if ch.isprintable())
    text = " ".join(text.split())
    return text[:max_length] if max_length else text


def clean_multiline(value, max_length):
    """Like ``clean_text`` but keeps line breaks (for notes and messages)."""
    if value is None:
        return ""
    lines = []
    for line in str(value).replace("\r\n", "\n").split("\n"):
        line = "".join(ch for ch in line if ch.isprintable())
        lines.append(" ".join(line.split()))
    return "\n".join(lines).strip()[: max_length + 1]


def is_checked(form, key):
    return str(form.get(key, "")).strip().lower() in ("on", "true", "1", "yes")


def _letters_and(value, extra):
    return bool(value) and all(ch.isalpha() or ch in extra for ch in value)


def validate_email(value):
    email = clean_text(value).lower()
    if not email:
        return email, "Enter your email address."
    if len(email) > 254 or not EMAIL_RE.match(email) or ".." in email:
        return email, "Enter a valid email address."
    return email, None


def validate_phone(value):
    raw = clean_text(value)
    if not raw:
        return "", "Enter your phone number."
    compact = re.sub(r"[ \-()]", "", raw)
    if not PHONE_RE.match(compact):
        return compact, "Enter a phone number with 10 to 15 digits."
    return compact, None


def validate_full_name(value):
    name = clean_text(value)
    if len(name) < 2 or len(name) > 100:
        return name, "Enter your full name (2 to 100 characters)."
    if not name[0].isalpha() or not _letters_and(name, NAME_EXTRA):
        return name, "Use letters, spaces, apostrophes, dots or hyphens only."
    return name, None


def validate_password(value, email=""):
    password = value or ""
    if len(password) < 8:
        return "Use at least 8 characters."
    if len(password) > 128:
        return "Use at most 128 characters."
    if not any(ch.isalpha() for ch in password) or not any(
        ch.isdigit() for ch in password
    ):
        return "Include at least one letter and one number."
    if password.lower() in COMMON_PASSWORDS:
        return "This password is too common. Choose a less predictable one."
    if email and password.lower() == email.lower():
        return "Your password cannot be the same as your email."
    return None


def validate_choice(value, allowed, message):
    value = clean_text(value)
    if value not in allowed:
        return value, message
    return value, None


def validate_place(value, label):
    place = clean_text(value)
    if len(place) < 2 or len(place) > 80:
        return place, "Enter %s (2 to 80 characters)." % label
    if not place[0].isalpha() or not _letters_and(place, PLACE_EXTRA):
        return place, "Use letters, spaces, dots, hyphens or apostrophes only."
    return string.capwords(place), None


def parse_date(value):
    try:
        return datetime.strptime(clean_text(value), "%Y-%m-%d").date()
    except ValueError:
        return None


def _set(errors, key, error):
    if error:
        errors[key] = error


def validate_login(form):
    email, error = validate_email(form.get("email"))
    errors = {}
    _set(errors, "email", error)
    password = form.get("password") or ""
    if not password:
        errors["password"] = "Enter your password."
    return {"email": email, "password": password}, errors


def validate_common_account(form, with_password=True):
    """Name, email, phone and (optionally) password fields."""
    cleaned, errors = {}, {}
    cleaned["full_name"], err = validate_full_name(form.get("full_name"))
    _set(errors, "full_name", err)
    cleaned["email"], err = validate_email(form.get("email"))
    _set(errors, "email", err)
    cleaned["phone"], err = validate_phone(form.get("phone"))
    _set(errors, "phone", err)
    if with_password:
        password = form.get("password") or ""
        confirm = form.get("confirm_password") or ""
        _set(errors, "password", validate_password(password, cleaned["email"]))
        if "password" not in errors and password != confirm:
            errors["confirm_password"] = "The passwords do not match."
        cleaned["password"] = password
    return cleaned, errors


def validate_donor_fields(form, today=None):
    """Fields shared by donor registration and the edit-profile form."""
    today = today or date.today()
    cleaned, errors = {}, {}
    cleaned["blood_group"], err = validate_choice(
        form.get("blood_group"), BLOOD_GROUPS, "Select a blood group."
    )
    _set(errors, "blood_group", err)

    age_text = clean_text(form.get("age"))
    cleaned["age"] = None
    if not age_text.isdigit():
        errors["age"] = "Enter your age as a whole number."
    else:
        age = int(age_text)
        if age < MIN_DONOR_AGE or age > MAX_DONOR_AGE:
            errors["age"] = "Donor age must be between %d and %d." % (
                MIN_DONOR_AGE,
                MAX_DONOR_AGE,
            )
        else:
            cleaned["age"] = age

    gender = clean_text(form.get("gender"))
    if gender and gender not in GENDERS:
        errors["gender"] = "Select one of the listed options."
    cleaned["gender"] = gender or None

    cleaned["state"], err = validate_choice(
        form.get("state"), INDIAN_STATES, "Select your state."
    )
    _set(errors, "state", err)
    cleaned["city"], err = validate_place(form.get("city"), "your city")
    _set(errors, "city", err)

    cleaned["last_donation_date"] = None
    date_text = clean_text(form.get("last_donation_date"))
    if date_text:
        parsed = parse_date(date_text)
        if parsed is None:
            errors["last_donation_date"] = "Enter a valid date."
        elif parsed > today:
            errors["last_donation_date"] = "The date cannot be in the future."
        elif parsed < today - timedelta(days=365 * 60):
            errors["last_donation_date"] = "Enter a more recent date."
        else:
            cleaned["last_donation_date"] = parsed

    cleaned["availability_status"], err = validate_choice(
        form.get("availability_status") or "available",
        AVAILABILITY_STATUSES,
        "Select an availability option.",
    )
    _set(errors, "availability_status", err)
    cleaned["visible_in_search"] = is_checked(form, "visible_in_search")
    cleaned["share_last_donation_date"] = is_checked(form, "share_last_donation_date")
    return cleaned, errors


def validate_registration(form, role):
    cleaned, errors = validate_common_account(form)
    if role == "donor":
        donor_cleaned, donor_errors = validate_donor_fields(form)
        cleaned.update(donor_cleaned)
        errors.update(donor_errors)
    if not is_checked(form, "accept_terms"):
        errors["accept_terms"] = "Accept the terms and privacy policy to continue."
    return cleaned, errors


def validate_account_update(form):
    cleaned, errors = validate_common_account(form, with_password=False)
    cleaned.pop("email", None)
    errors.pop("email", None)
    return cleaned, errors


def validate_password_change(form, email=""):
    errors = {}
    current = form.get("current_password") or ""
    new = form.get("new_password") or ""
    confirm = form.get("confirm_password") or ""
    if not current:
        errors["current_password"] = "Enter your current password."
    _set(errors, "new_password", validate_password(new, email))
    if "new_password" not in errors and new != confirm:
        errors["confirm_password"] = "The passwords do not match."
    if "new_password" not in errors and current and new == current:
        errors["new_password"] = "Choose a password different from the current one."
    return {"current_password": current, "new_password": new}, errors


def validate_password_reset(form, email=""):
    errors = {}
    new = form.get("password") or ""
    confirm = form.get("confirm_password") or ""
    _set(errors, "password", validate_password(new, email))
    if "password" not in errors and new != confirm:
        errors["confirm_password"] = "The passwords do not match."
    return {"password": new}, errors


def validate_blood_request(form, today=None):
    today = today or date.today()
    cleaned, errors = {}, {}
    cleaned["blood_group"], err = validate_choice(
        form.get("blood_group"), BLOOD_GROUPS, "Select the blood group needed."
    )
    _set(errors, "blood_group", err)

    units_text = clean_text(form.get("units_required"))
    cleaned["units_required"] = None
    if not units_text.isdigit() or not 1 <= int(units_text) <= MAX_UNITS_PER_REQUEST:
        errors["units_required"] = "Enter a number of units between 1 and %d." % (
            MAX_UNITS_PER_REQUEST
        )
    else:
        cleaned["units_required"] = int(units_text)

    hospital = clean_text(form.get("hospital_name"))
    if len(hospital) > 150:
        errors["hospital_name"] = "Use at most 150 characters."
    cleaned["hospital_name"] = hospital or None

    cleaned["state"], err = validate_choice(
        form.get("state"), INDIAN_STATES, "Select the state."
    )
    _set(errors, "state", err)
    cleaned["city"], err = validate_place(form.get("city"), "the city")
    _set(errors, "city", err)

    cleaned["required_by"] = None
    parsed = parse_date(form.get("required_by"))
    if parsed is None:
        errors["required_by"] = "Enter the date blood is needed."
    elif parsed < today:
        errors["required_by"] = "The date cannot be in the past."
    elif parsed > today + timedelta(days=365):
        errors["required_by"] = "Choose a date within the next year."
    else:
        cleaned["required_by"] = parsed

    cleaned["urgency"], err = validate_choice(
        form.get("urgency") or "normal", URGENCY_LEVELS, "Select an urgency level."
    )
    _set(errors, "urgency", err)

    notes = clean_multiline(form.get("notes"), 500)
    if len(notes) > 500:
        errors["notes"] = "Use at most 500 characters."
    cleaned["notes"] = notes or None
    return cleaned, errors


def validate_contact_message(form):
    errors = {}
    message = clean_multiline(form.get("message"), 500)
    if len(message) < 10:
        errors["message"] = "Write a short message (at least 10 characters)."
    elif len(message) > 500:
        errors["message"] = "Use at most 500 characters."
    blood_request_id = None
    raw = clean_text(form.get("blood_request_id"))
    if raw:
        if raw.isdigit():
            blood_request_id = int(raw)
        else:
            errors["blood_request_id"] = "Choose one of your requests."
    return {"message": message, "blood_request_id": blood_request_id}, errors


def validate_reason(form, field="reason", required=True):
    reason = clean_text(form.get(field), 201)
    errors = {}
    if required and not reason:
        errors[field] = "Enter a short reason."
    elif len(reason) > 200:
        errors[field] = "Use at most 200 characters."
    return {field: reason}, errors


def validate_notice(form):
    errors = {}
    title = clean_text(form.get("title"))
    message = clean_multiline(form.get("message"), 500)
    audience = clean_text(form.get("audience"))
    if not title or len(title) > 150:
        errors["title"] = "Enter a title of up to 150 characters."
    if not message or len(message) > 500:
        errors["message"] = "Enter a message of up to 500 characters."
    if audience not in ("all", "donor", "recipient"):
        errors["audience"] = "Choose who should receive this notice."
    return {"title": title, "message": message, "audience": audience}, errors


def validate_search_filters(args):
    """Validate donor-search query parameters. Blank values mean 'no filter'."""
    cleaned, errors = {}, {}
    blood_group = clean_text(args.get("blood_group"))
    if blood_group and blood_group not in BLOOD_GROUPS:
        errors["blood_group"] = "Choose a valid blood group."
        blood_group = ""
    cleaned["blood_group"] = blood_group

    state = clean_text(args.get("state"))
    if state and state not in INDIAN_STATES:
        errors["state"] = "Choose a valid state."
        state = ""
    cleaned["state"] = state

    city = clean_text(args.get("city"), 81)
    if len(city) > 80:
        errors["city"] = "Use at most 80 characters."
        city = ""
    cleaned["city"] = city

    availability = clean_text(args.get("availability"))
    if availability and availability not in AVAILABILITY_STATUSES:
        errors["availability"] = "Choose a valid availability option."
        availability = ""
    cleaned["availability"] = availability

    name = clean_text(args.get("q"), 101)
    if len(name) > 100:
        errors["q"] = "Use at most 100 characters."
        name = ""
    cleaned["q"] = name

    sort = clean_text(args.get("sort")) or "availability"
    if sort not in SORT_OPTIONS:
        errors["sort"] = "Choose a valid sort option."
        sort = "availability"
    cleaned["sort"] = sort
    return cleaned, errors
