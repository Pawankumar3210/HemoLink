"""Jinja filters, globals and the navigation model."""

from datetime import date, datetime

from flask import g, request, url_for
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from app.constants import (
    AVAILABILITY_STATUSES,
    BLOOD_GROUPS,
    GENDERS,
    INDIAN_STATES,
    LABELS,
    ROLE_ADMIN,
    ROLE_DONOR,
    ROLE_RECIPIENT,
    URGENCY_LEVELS,
)

NAV = {
    ROLE_DONOR: [
        ("Dashboard", "dashboard.donor", "home", ()),
        ("My profile", "donors.profile", "user", ("donors.edit_profile",)),
        ("Availability", "donors.availability", "toggle", ()),
        ("Contact requests", "contact.incoming", "inbox", ("contact.detail",)),
        ("History", "contact.history", "clock", ()),
        ("Open requests", "donors.open_requests", "list", ("blood_requests.detail",)),
        ("Notifications", "notifications.index", "bell", ()),
        ("Account", "dashboard.account", "settings", ()),
    ],
    ROLE_RECIPIENT: [
        ("Dashboard", "dashboard.recipient", "home", ()),
        ("Find donors", "donors.search", "search", ("donors.detail",)),
        ("New request", "blood_requests.create", "plus", ()),
        (
            "My requests",
            "blood_requests.index",
            "list",
            ("blood_requests.detail", "blood_requests.edit"),
        ),
        (
            "Contact tracking",
            "contact.tracking",
            "users",
            ("contact.detail", "contact.request_form"),
        ),
        ("Notifications", "notifications.index", "bell", ()),
        ("Account", "dashboard.account", "settings", ()),
    ],
    ROLE_ADMIN: [
        ("Overview", "admin.index", "home", ()),
        ("Users", "admin.users", "users", ("admin.user_detail",)),
        ("Donors", "admin.donors", "droplet", ()),
        ("Blood requests", "admin.requests", "list", ()),
        ("Contact requests", "admin.contacts", "inbox", ()),
        ("Audit log", "admin.audit", "shield", ()),
        ("Notices", "admin.notices", "bell", ()),
        ("System", "admin.system", "activity", ()),
        ("Account", "dashboard.account", "settings", ()),
    ],
}


def label(value):
    if value is None or value == "":
        return ""
    return LABELS.get(value, str(value).replace("_", " ").capitalize())


def fmt_date(value):
    if isinstance(value, (datetime, date)):
        return value.strftime("%d %b %Y")
    return "Not set"


def fmt_datetime(value):
    if isinstance(value, datetime):
        return value.strftime("%d %b %Y, %H:%M UTC")
    return "Not set"


def page_url(page):
    """URL of the current page with ``page`` swapped in, keeping all filters."""
    values = dict(request.view_args or {})
    values.update(request.args.to_dict(flat=True))
    values["page"] = page
    return url_for(request.endpoint, **values)


def initials(name):
    parts = [p for p in (name or "").split() if p]
    return "".join(p[0] for p in parts[:2]).upper() or "H"


def _unread_count():
    """Unread notifications for the signed-in user, computed once per request."""
    if "unread_count" not in g:
        count = 0
        if current_user.is_authenticated:
            from app.services.notifications import unread_count

            try:
                count = unread_count(current_user.id)
            except SQLAlchemyError:
                count = 0
        g.unread_count = count
    return g.unread_count


def nav_items():
    if not current_user.is_authenticated:
        return []
    items = []
    for text, endpoint, icon, also in NAV.get(current_user.role, []):
        active = request.endpoint == endpoint or request.endpoint in also
        items.append(
            {
                "label": text,
                "endpoint": endpoint,
                "icon": icon,
                "active": active,
                "is_notifications": endpoint == "notifications.index",
            }
        )
    return items


def register_template_helpers(app):
    app.jinja_env.filters["label"] = label
    app.jinja_env.filters["fmt_date"] = fmt_date
    app.jinja_env.filters["fmt_datetime"] = fmt_datetime
    app.jinja_env.filters["initials"] = initials
    app.jinja_env.globals["page_url"] = page_url
    app.jinja_env.globals["unread_count"] = _unread_count
    app.jinja_env.globals["nav_items"] = nav_items

    @app.context_processor
    def inject_constants():
        return {
            "APP_NAME": "HemoLink",
            "BLOOD_GROUPS": BLOOD_GROUPS,
            "INDIAN_STATES": INDIAN_STATES,
            "GENDERS": GENDERS,
            "AVAILABILITY_OPTIONS": [(v, LABELS[v]) for v in AVAILABILITY_STATUSES],
            "URGENCY_OPTIONS": [(v, LABELS[v]) for v in URGENCY_LEVELS],
            "current_year": datetime.now().year,
            "today_iso": date.today().isoformat(),
        }
