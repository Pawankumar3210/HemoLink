"""Administrator dashboard, user management, moderation and audit logging."""

from sqlalchemy import select

from app.extensions import db
from app.models import AuditLog, BloodRequest, Notification, User
from app.services.stats import platform_stats
from tests.helpers import (
    PASSWORD,
    count,
    create_blood_request,
    create_contact,
    create_user,
    fetch,
    get_email,
    get_phone,
    logged_in_client,
    notifications_for,
)


def admin_client(app):
    return logged_in_client(app, create_user(app, "admin", name="Admin Alex"))


def audit_actions(app):
    with app.app_context():
        return [row.action for row in db.session.scalars(select(AuditLog))]


def test_dashboard_statistics_come_from_database(app):
    create_user(app, "donor", availability="available")
    create_user(app, "donor", availability="available")
    create_user(app, "donor", availability="temporarily_unavailable")
    create_user(app, "donor", availability="unavailable")
    recipient = create_user(app, "recipient")
    create_user(app, "recipient")
    create_user(app, "donor", status="deleted")
    create_blood_request(app, recipient)
    create_blood_request(app, recipient)
    create_blood_request(app, recipient, status="fulfilled")
    donor = create_user(app, "donor")
    create_contact(app, donor, recipient)
    with app.app_context():
        stats = platform_stats()
    assert stats["donors"] == 5 and stats["recipients"] == 2
    assert stats["total_users"] == 7  # the deleted donor is not counted
    assert stats["available_donors"] == 3
    assert stats["temporarily_unavailable_donors"] == 1
    assert stats["total_requests"] == 3 and stats["open_requests"] == 2
    assert stats["fulfilled_requests"] == 1 and stats["pending_contacts"] == 1
    client = admin_client(app)
    page = client.get("/admin/")
    assert page.status_code == 200 and b"Registered users" in page.data


def test_user_filters(app):
    create_user(app, "donor", name="Findable Donor")
    create_user(app, "recipient", name="Findable Recipient")
    create_user(app, "recipient", name="Suspended Person", status="suspended")
    client = admin_client(app)
    by_role = client.get("/admin/users", query_string={"role": "donor"}).data
    assert b"Findable Donor" in by_role and b"Findable Recipient" not in by_role
    by_status = client.get("/admin/users", query_string={"status": "suspended"}).data
    assert b"Suspended Person" in by_status and b"Findable Donor" not in by_status
    by_query = client.get("/admin/users", query_string={"q": "findable rec"}).data
    assert b"Findable Recipient" in by_query and b"Findable Donor" not in by_query


def test_donor_listing_filters(app):
    create_user(app, "donor", name="Group A", blood_group="A+")
    create_user(
        app, "donor", name="Group O", blood_group="O-", city="Pune", state="Maharashtra"
    )
    client = admin_client(app)
    page = client.get("/admin/donors", query_string={"blood_group": "O-"}).data
    assert b"Group O" in page and b"Group A" not in page
    page = client.get("/admin/donors", query_string={"city": "pun"}).data
    assert b"Group O" in page and b"Group A" not in page


def test_suspend_and_reactivate_user_with_audit_log(app):
    victim = create_user(app, "donor")
    victim_client = logged_in_client(app, victim)
    admin = admin_client(app)
    assert admin.post("/admin/users/%d/suspend" % victim).status_code == 302
    assert fetch(app, User, victim).account_status == "suspended"
    # existing sessions are cut off immediately
    assert victim_client.get("/dashboard/donor").status_code == 302
    login = app.test_client().post(
        "/login", data={"email": get_email(app, victim), "password": PASSWORD}
    )
    assert b"suspended" in login.data
    assert admin.post("/admin/users/%d/reactivate" % victim).status_code == 302
    assert fetch(app, User, victim).account_status == "active"
    assert logged_in_client(app, victim).get("/dashboard/donor").status_code == 200
    actions = audit_actions(app)
    assert "user.suspend" in actions and "user.reactivate" in actions
    assert any(n.title == "Account reactivated" for n in notifications_for(app, victim))


def test_suspended_donor_disappears_from_search(app):
    victim = create_user(app, "donor", name="Vanishing Vic")
    recipient = logged_in_client(app, create_user(app, "recipient"))
    assert b"Vanishing Vic" in recipient.get("/donors/search").data
    admin_client(app).post("/admin/users/%d/suspend" % victim)
    assert b"Vanishing Vic" not in recipient.get("/donors/search").data


def test_admin_accounts_cannot_be_suspended(app):
    other_admin = create_user(app, "admin")
    admin = admin_client(app)
    response = admin.post(
        "/admin/users/%d/suspend" % other_admin, follow_redirects=True
    )
    assert b"cannot be changed" in response.data
    assert fetch(app, User, other_admin).account_status == "active"


def test_double_suspend_and_unknown_user(app):
    victim = create_user(app, "recipient")
    admin = admin_client(app)
    admin.post("/admin/users/%d/suspend" % victim)
    again = admin.post("/admin/users/%d/suspend" % victim, follow_redirects=True)
    assert b"already suspended" in again.data
    assert admin.post("/admin/users/99999/suspend").status_code == 404
    assert admin.get("/admin/users/99999").status_code == 404


def test_user_detail_page(app):
    donor = create_user(app, "donor", name="Detail Dee")
    page = admin_client(app).get("/admin/users/%d" % donor)
    assert page.status_code == 200 and b"Detail Dee" in page.data


def test_reject_request_requires_reason_and_notifies_owner(app):
    owner = create_user(app, "recipient")
    request_id = create_blood_request(app, owner)
    admin = admin_client(app)
    no_reason = admin.post(
        "/admin/requests/%d/status" % request_id, data={"status": "rejected"}
    )
    assert no_reason.status_code == 302
    assert fetch(app, BloodRequest, request_id).status == "open"
    admin.post(
        "/admin/requests/%d/status" % request_id,
        data={"status": "rejected", "reason": "Contains a patient name"},
    )
    row = fetch(app, BloodRequest, request_id)
    assert row.status == "rejected" and row.moderation_note == "Contains a patient name"
    assert "request.rejected" in audit_actions(app)
    notice = [n for n in notifications_for(app, owner) if "rejected" in n.title]
    assert notice and "Contains a patient name" in notice[0].message
    owner_page = logged_in_client(app, owner).get("/requests/%d" % request_id)
    assert b"Contains a patient name" in owner_page.data


def test_admin_can_reopen_rejected_request_but_not_others(app):
    owner = create_user(app, "recipient")
    rejected = create_blood_request(app, owner, status="rejected")
    cancelled = create_blood_request(app, owner, status="cancelled")
    admin = admin_client(app)
    admin.post("/admin/requests/%d/status" % rejected, data={"status": "open"})
    assert fetch(app, BloodRequest, rejected).status == "open"
    admin.post("/admin/requests/%d/status" % cancelled, data={"status": "open"})
    assert fetch(app, BloodRequest, cancelled).status == "cancelled"


def test_request_listing_filters(app):
    owner = create_user(app, "recipient")
    create_blood_request(app, owner, blood_group="AB-", city="Kochi", state="Kerala")
    create_blood_request(app, owner, blood_group="O+", status="fulfilled")
    admin = admin_client(app)
    page = admin.get("/admin/requests", query_string={"blood_group": "AB-"}).data
    assert b"Kochi" in page and b"Bengaluru" not in page
    page = admin.get("/admin/requests", query_string={"status": "fulfilled"}).data
    assert b"Bengaluru" in page and b"Kochi" not in page
    page = admin.get("/admin/requests", query_string={"city": "koc"}).data
    assert b"Kochi" in page


def test_contact_overview_hides_phone_numbers(app):
    donor = create_user(app, "donor", name="Overview Donor")
    recipient = create_user(app, "recipient", name="Overview Recipient")
    create_contact(app, donor, recipient, status="accepted")
    page = admin_client(app).get("/admin/contacts").data
    assert b"Overview Donor" in page and b"Overview Recipient" in page
    assert get_phone(app, donor).encode() not in page


def test_audit_log_page_and_filter(app):
    victim = create_user(app, "recipient")
    admin = admin_client(app)
    admin.post("/admin/users/%d/suspend" % victim)
    page = admin.get("/admin/audit").data
    assert b"user.suspend" in page and b"Admin Alex" in page
    filtered = admin.get("/admin/audit", query_string={"action": "request."}).data
    assert b"user.suspend" not in filtered


def test_audit_entries_contain_no_secrets(app):
    victim = create_user(app, "recipient")
    admin_client(app).post("/admin/users/%d/suspend" % victim)
    with app.app_context():
        for row in db.session.scalars(select(AuditLog)):
            blob = " ".join(str(v) for v in (row.action, row.details, row.entity_type))
            assert "password" not in blob.lower() and "token" not in blob.lower()


def test_broadcast_notice(app):
    donors = [create_user(app, "donor") for _ in range(2)]
    recipient = create_user(app, "recipient")
    create_user(app, "donor", status="suspended")
    admin = admin_client(app)
    response = admin.post(
        "/admin/notices",
        data={
            "title": "Maintenance",
            "message": "Planned downtime tonight.",
            "audience": "donor",
        },
    )
    assert response.status_code == 302
    for donor in donors:
        assert any(n.title == "Maintenance" for n in notifications_for(app, donor))
    assert not any(n.title == "Maintenance" for n in notifications_for(app, recipient))
    assert count(app, Notification, Notification.title == "Maintenance") == 2
    assert "notice.broadcast" in audit_actions(app)
    bad = admin.post(
        "/admin/notices", data={"title": "", "message": "x", "audience": "everyone"}
    )
    assert bad.status_code == 400


def test_system_page_shows_no_secrets(app):
    page = admin_client(app).get("/admin/system")
    assert page.status_code == 200 and b"Database" in page.data
    assert app.config["SECRET_KEY"].encode() not in page.data
    assert b"mysql+pymysql" not in page.data
