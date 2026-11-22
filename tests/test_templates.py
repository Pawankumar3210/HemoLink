"""Template integrity: every template compiles and every url_for target exists."""

import re
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "app" / "templates"


def test_all_templates_compile(app):
    names = [n for n in app.jinja_env.list_templates() if n.endswith(".html")]
    assert len(names) > 40
    for name in names:
        app.jinja_env.get_template(name)


def test_every_url_for_in_templates_points_to_a_real_endpoint(app):
    endpoints = set(app.view_functions)
    pattern = re.compile(r"""url_for\(\s*['"]([\w.]+)['"]""")
    missing = []
    for path in TEMPLATE_DIR.rglob("*.html"):
        for endpoint in pattern.findall(path.read_text()):
            if endpoint not in endpoints:
                missing.append((path.name, endpoint))
    assert not missing, missing


def test_navigation_endpoints_exist(app):
    from app.template_helpers import NAV

    endpoints = set(app.view_functions)
    for role, items in NAV.items():
        for label, endpoint, icon, also in items:
            assert endpoint in endpoints, (role, endpoint)
            assert set(also) <= endpoints, (role, also)


def test_all_required_pages_have_routes(app):
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    required = {
        "/", "/about", "/how-it-works", "/sdg-3", "/login", "/register/donor",
        "/register/recipient", "/forgot-password", "/reset-password/<token>",
        "/privacy", "/terms", "/dashboard/donor", "/donor/profile",
        "/donor/profile/edit", "/donor/availability", "/contact/incoming",
        "/contact/history", "/notifications/", "/account", "/dashboard/recipient",
        "/donors/search", "/donors/<int:profile_id>", "/requests/new", "/requests/",
        "/requests/<int:request_id>", "/contact/tracking", "/admin/",
        "/admin/users", "/admin/donors", "/admin/requests", "/admin/contacts",
        "/admin/audit", "/admin/system", "/health/live", "/health/ready",
    }
    assert required <= rules, required - rules
