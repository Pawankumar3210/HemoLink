"""Shared test helpers: object factories and small request utilities."""

import itertools
import re
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (
    BloodRequest,
    ContactRequest,
    DonorProfile,
    Notification,
    User,
)

PASSWORD = "Passw0rd!x"
# Hash once: scrypt is deliberately slow and every factory user shares it.
PASSWORD_HASH = generate_password_hash(PASSWORD)
_counter = itertools.count(1)


def create_user(app, role="recipient", email=None, name=None, status="active", **extra):
    """Create a user (and donor profile for donors). Returns the user id."""
    n = next(_counter)
    with app.app_context():
        user = User(
            full_name=name or "Test %s %d" % (role.title(), n),
            email=email or "%s%d@example.com" % (role, n),
            phone=extra.pop("phone", "+9190000%05d" % n),
            role=role,
            account_status=status,
            password_hash=PASSWORD_HASH,
        )
        if role == "donor":
            user.donor_profile = DonorProfile(
                blood_group=extra.pop("blood_group", "O+"),
                age=extra.pop("age", 30),
                gender=extra.pop("gender", None),
                state=extra.pop("state", "Karnataka"),
                city=extra.pop("city", "Bengaluru"),
                last_donation_date=extra.pop("last_donation_date", None),
                availability_status=extra.pop("availability", "available"),
                visible_in_search=extra.pop("visible", True),
                share_last_donation_date=extra.pop("share_date", False),
            )
        db.session.add(user)
        db.session.commit()
        return user.id


def get_email(app, user_id):
    with app.app_context():
        return db.session.get(User, user_id).email


def get_phone(app, user_id):
    with app.app_context():
        return db.session.get(User, user_id).phone


def profile_id(app, user_id):
    with app.app_context():
        return db.session.get(User, user_id).donor_profile.id


def login(client, app, user_id, password=PASSWORD):
    return client.post(
        "/login",
        data={"email": get_email(app, user_id), "password": password},
    )


def logged_in_client(app, user_id):
    client = app.test_client()
    response = login(client, app, user_id)
    assert response.status_code == 302, response.data[:300]
    return client


def create_blood_request(app, requester_id, **overrides):
    values = dict(
        requester_id=requester_id,
        blood_group="O+",
        units_required=2,
        hospital_name="City Hospital",
        state="Karnataka",
        city="Bengaluru",
        required_by=date.today() + timedelta(days=3),
        urgency="normal",
        status="open",
        notes=None,
    )
    values.update(overrides)
    with app.app_context():
        blood_request = BloodRequest(**values)
        db.session.add(blood_request)
        db.session.commit()
        return blood_request.id


def create_contact(app, donor_id, recipient_id, status="pending", **overrides):
    values = dict(
        donor_id=donor_id,
        recipient_id=recipient_id,
        message="Please help, we need a donor urgently.",
        status=status,
    )
    values.update(overrides)
    with app.app_context():
        contact = ContactRequest(**values)
        db.session.add(contact)
        db.session.commit()
        return contact.id


def fetch(app, model, object_id):
    """Load a fresh copy of a row and return it with attributes loaded."""
    with app.app_context():
        obj = db.session.get(model, object_id)
        if obj is not None:
            db.session.expire_all()
            db.session.refresh(obj)
            db.session.expunge(obj)
        return obj


def count(app, model, *conditions):
    from sqlalchemy import func, select

    with app.app_context():
        stmt = select(func.count()).select_from(model)
        if conditions:
            stmt = stmt.where(*conditions)
        return db.session.scalar(stmt)


def notifications_for(app, user_id):
    from sqlalchemy import select

    with app.app_context():
        rows = db.session.scalars(
            select(Notification).where(Notification.user_id == user_id)
        )
        return list(rows)


def donor_form(**overrides):
    form = dict(
        full_name="Asha Kumar",
        email="asha@example.com",
        phone="+919876543210",
        password=PASSWORD,
        confirm_password=PASSWORD,
        blood_group="O+",
        age="30",
        state="Karnataka",
        city="Bengaluru",
        availability_status="available",
        visible_in_search="on",
        accept_terms="on",
    )
    form.update(overrides)
    return form


def recipient_form(**overrides):
    form = dict(
        full_name="Rohan Mehta",
        email="rohan@example.com",
        phone="+919812345678",
        password=PASSWORD,
        confirm_password=PASSWORD,
        accept_terms="on",
    )
    form.update(overrides)
    return form


def request_form(**overrides):
    form = dict(
        blood_group="A+",
        units_required="2",
        hospital_name="City Hospital",
        state="Karnataka",
        city="Mysuru",
        required_by=(date.today() + timedelta(days=4)).isoformat(),
        urgency="high",
        notes="Ward 4",
    )
    form.update(overrides)
    return form


def extract_token(text):
    match = re.search(r"/reset-password/([A-Za-z0-9_-]+)", text)
    assert match, "no reset link found"
    return match.group(1)
