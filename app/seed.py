"""Synthetic demonstration data. Every demo account uses a reserved email domain."""

import random
import secrets
from datetime import date, timedelta

from sqlalchemy import delete, select

from app.constants import (
    AVAILABLE,
    BLOOD_GROUPS,
    CONTACT_ACCEPTED,
    CONTACT_DECLINED,
    CONTACT_PENDING,
    REQUEST_FULFILLED,
    REQUEST_OPEN,
    ROLE_DONOR,
    ROLE_RECIPIENT,
    TEMPORARILY_UNAVAILABLE,
    UNAVAILABLE,
)
from app.extensions import db
from app.models import (
    BloodRequest,
    ContactRequest,
    DonorProfile,
    Notification,
    User,
)
from app.utils.time import utcnow

DEMO_DOMAIN = "demo.hemolink.example"

FIRST_NAMES = [
    "Aarav",
    "Diya",
    "Kabir",
    "Meera",
    "Rohan",
    "Isha",
    "Vikram",
    "Anaya",
    "Arjun",
    "Nisha",
    "Dev",
    "Tara",
    "Rahul",
    "Sana",
    "Karan",
    "Pooja",
    "Imran",
    "Lakshmi",
    "Nikhil",
    "Zoya",
    "Suresh",
    "Anjali",
    "Faisal",
    "Riya",
]
LAST_NAMES = [
    "Demo",
    "Sample",
    "Example",
    "Placeholder",
    "Testwell",
    "Fictional",
]
LOCATIONS = [
    ("Karnataka", "Bengaluru"),
    ("Karnataka", "Mysuru"),
    ("Maharashtra", "Mumbai"),
    ("Maharashtra", "Pune"),
    ("Tamil Nadu", "Chennai"),
    ("Telangana", "Hyderabad"),
    ("Delhi", "New Delhi"),
    ("Kerala", "Kochi"),
]
STATES = [AVAILABLE, AVAILABLE, AVAILABLE, TEMPORARILY_UNAVAILABLE, UNAVAILABLE]


def _phone(index):
    """Obviously fictional numbers (they start with 0, so are not dialable)."""
    return "+910000%06d" % index


def demo_user_ids():
    return list(
        db.session.scalars(select(User.id).where(User.email.like("%@" + DEMO_DOMAIN)))
    )


def remove_demo_data():
    """Delete only accounts on the demo email domain (cascades to their records)."""
    ids = demo_user_ids()
    if not ids:
        return 0
    db.session.execute(
        delete(ContactRequest).where(
            ContactRequest.donor_id.in_(ids) | ContactRequest.recipient_id.in_(ids)
        )
    )
    db.session.execute(delete(BloodRequest).where(BloodRequest.requester_id.in_(ids)))
    db.session.execute(delete(Notification).where(Notification.user_id.in_(ids)))
    db.session.execute(delete(DonorProfile).where(DonorProfile.user_id.in_(ids)))
    db.session.execute(delete(User).where(User.id.in_(ids)))
    db.session.commit()
    return len(ids)


def seed_demo(password=None):
    """Create demo donors, recipients, requests, contacts and notifications.

    Returns ``(password, summary)``. A random password is generated if none is
    supplied, so no credential is stored in the repository.
    """
    if demo_user_ids():
        raise RuntimeError("Demo data already exists. Use --reset to recreate it.")
    rng = random.Random(2026)
    password = password or secrets.token_urlsafe(12) + "9a"
    today = date.today()

    donors = []
    for index in range(24):
        state, city = LOCATIONS[index % len(LOCATIONS)]
        name = "%s %s" % (FIRST_NAMES[index], rng.choice(LAST_NAMES))
        user = User(
            full_name=name,
            email="donor%02d@%s" % (index + 1, DEMO_DOMAIN),
            phone=_phone(index + 1),
            role=ROLE_DONOR,
        )
        user.set_password(password)
        last = today - timedelta(days=rng.randint(40, 400)) if index % 4 else None
        user.donor_profile = DonorProfile(
            blood_group=BLOOD_GROUPS[index % len(BLOOD_GROUPS)],
            age=rng.randint(20, 55),
            gender=rng.choice(["Female", "Male", "Other", None]),
            state=state,
            city=city,
            last_donation_date=last,
            availability_status=STATES[index % len(STATES)],
            visible_in_search=index % 7 != 6,
            share_last_donation_date=index % 3 == 0,
        )
        db.session.add(user)
        donors.append(user)

    recipients = []
    for index in range(4):
        user = User(
            full_name="%s Recipient" % FIRST_NAMES[20 + index],
            email="recipient%02d@%s" % (index + 1, DEMO_DOMAIN),
            phone=_phone(100 + index),
            role=ROLE_RECIPIENT,
        )
        user.set_password(password)
        db.session.add(user)
        recipients.append(user)
    db.session.flush()

    requests = []
    plans = [
        ("O+", "Karnataka", "Bengaluru", "urgent", REQUEST_OPEN),
        ("A-", "Maharashtra", "Pune", "high", REQUEST_OPEN),
        ("B+", "Tamil Nadu", "Chennai", "normal", REQUEST_OPEN),
        ("AB+", "Telangana", "Hyderabad", "normal", REQUEST_FULFILLED),
        ("O-", "Delhi", "New Delhi", "urgent", REQUEST_OPEN),
        ("A+", "Kerala", "Kochi", "high", REQUEST_OPEN),
    ]
    for index, (group, state, city, urgency, status) in enumerate(plans):
        blood_request = BloodRequest(
            requester_id=recipients[index % len(recipients)].id,
            blood_group=group,
            units_required=rng.randint(1, 3),
            hospital_name="Demo General Hospital",
            state=state,
            city=city,
            required_by=today + timedelta(days=rng.randint(2, 20)),
            urgency=urgency,
            status=status,
            notes="Demonstration request created by the seed command.",
        )
        db.session.add(blood_request)
        requests.append(blood_request)
    db.session.flush()

    now = utcnow()
    contact_plans = [
        (0, 0, CONTACT_PENDING),
        (1, 0, CONTACT_ACCEPTED),
        (2, 1, CONTACT_DECLINED),
        (3, 2, CONTACT_PENDING),
        (4, 3, CONTACT_ACCEPTED),
    ]
    for donor_index, recipient_index, status in contact_plans:
        donor = donors[donor_index]
        contact = ContactRequest(
            donor_id=donor.id,
            recipient_id=recipients[recipient_index].id,
            blood_request_id=requests[recipient_index].id,
            message="Hello, we are looking for a donor. Could you help? (demo)",
            status=status,
            responded_at=None if status == CONTACT_PENDING else now,
            donor_consent_at=now if status == CONTACT_ACCEPTED else None,
        )
        db.session.add(contact)
        db.session.flush()
        db.session.add(
            Notification(
                user_id=donor.id,
                title="New contact request",
                message="%s would like to contact you."
                % recipients[recipient_index].full_name,
                related_type="contact_request",
                related_id=contact.id,
            )
        )
    db.session.commit()
    summary = {
        "donors": len(donors),
        "recipients": len(recipients),
        "requests": len(requests),
        "contacts": len(contact_plans),
    }
    return password, summary
