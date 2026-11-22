# Testing

## Strategy

* **Unit tests** (`test_validation.py`, `test_utils.py`): pure functions (validation,
  rate limiter, redirect safety, configuration). No database.
* **Integration tests** (everything else): the real Flask app, real SQLAlchemy models and a
  real database, driven through the Flask test client: authentication, authorisation,
  donor management, search, blood requests, the contact/consent workflow, notifications,
  admin operations, security headers, CSRF, rate limiting, health checks, CLI commands and
  template integrity.
* **Database matrix.** Locally the suite uses in-memory SQLite (fast). In CI it runs on a
  MySQL 8 service container, with the schema built from the Alembic migrations
  (`TEST_USE_MIGRATIONS=1`), so MySQL compatibility and the migrations are verified by the
  same tests.

The suite contains about 180 test functions (roughly 240 cases with parametrisation).

| File | Covers |
|---|---|
| `test_auth.py` | Registration, duplicate/invalid input, password hashing, login/logout, generic errors, suspended users, `next` redirects, password-reset flow (single use, expiry, hashed tokens, enumeration) |
| `test_authorization.py` | Role matrix for every protected page; admin POSTs forbidden to non-admins; role escalation attempts; IDOR checks on requests, contact requests and profiles |
| `test_donors.py` | Profile create/update, validation, availability, visibility, account update/password change/deletion |
| `test_search.py` | Every filter and combination, empty results, LIKE wildcards, hidden/suspended/deleted exclusion, privacy of contact details, last-donation visibility, pagination, sorting, malformed input |
| `test_blood_requests.py` | Create/validate/edit/cancel/fulfil, ownership, status rules, notifications, escaping, donor discovery |
| `test_contact_requests.py` | Create, duplicates, cooldown after decline, accept/decline/withdraw/revoke, double-accept, unauthorised responders, phone visibility before/after consent and after revocation or suspension |
| `test_admin.py` | Statistics, filters, suspend/reactivate (immediate logout), request moderation, audit log, notices, system page |
| `test_notifications.py` | Counts, list, mark read/all, ownership, destinations, safe `next` |
| `test_security.py` | CSRF, headers, HSTS, cookie flags, rate limits, health/readiness, error pages, XSS, SQL-injection attempts, CSP-safe markup |
| `test_mailer.py` | SMTP path (TLS, login), failure handling, dev outbox, release id |
| `test_cli.py` | `create-admin` (hashing, duplicates, validation), `seed-demo` (marking, repeatability, production refusal, never touches real accounts) |
| `test_templates.py`, `test_public_pages.py` | Every template compiles; every `url_for` target exists; every required route exists; landing statistics are live |

## Running

```bash
pytest                                              # SQLite, quick
pytest --cov=app --cov-report=term-missing          # with coverage
TEST_DATABASE_URL="mysql+pymysql://user:pw@localhost/hemolink_test?charset=utf8mb4" \
TEST_USE_MIGRATIONS=1 pytest                        # MySQL + migrations
docker compose run --rm test                        # MySQL in Docker
```

Safety: the fixtures drop and recreate tables, so they **refuse to run** unless the
database name contains `test` (SQLite is always allowed).

Coverage: the CI gate is 80% (`--cov-fail-under=80`). Nothing meaningful is excluded
from measurement (`.coveragerc` omits only tests and defensive `__main__` lines).

## Code quality

```bash
black .                                   # format (CI runs black --check)
flake8 app tests scripts run.py           # configuration in .flake8 (88 columns)
```

Configuration lives in `pyproject.toml` (Black) and `.flake8`. Migrations are excluded
from both because they are generated code.

## What was and was not verified when this repository was produced

The generating environment had no network access and only Flask/Jinja2 installed, so the
suite could not be executed end to end. Honest status:

| Check | Status |
|---|---|
| Python syntax of every module | Verified (compiled) |
| Every template compiles; every `url_for` endpoint and its required arguments exist (61 endpoints) | Verified by script |
| 80 template renders (every page, many states) with fake data on real Flask/Jinja, including macros and includes | Verified; surfaced and fixed a missing `endblock` and a pagination-name clash |
| Rendered markup: no inline scripts/styles (CSP-safe), no contact details in donor cards, escaping | Verified |
| Validation and utility unit tests (47 cases) | **Executed and passing** (this found and fixed a whitespace bug in `clean_text`) |
| Migration versus models (tables, columns, nullability, indexes, constraint and FK names) | Verified by script: 0 differences |
| YAML validity of both workflows and Compose; shell syntax of scripts | Verified |
| Line length, unused imports and unused locals (approximation of Flake8) | Verified by script |
| Database-backed pytest suite (SQLAlchemy, Flask-Login, Flask-WTF) | **Not run**: written against the implemented behaviour; first real run is in your CI or locally |
| Flake8 / Black exact output | **Not run**: run `black .` once before the first push |
| Docker build, Compose, MySQL, GitHub Actions, deployment | **Not run** |

Expect a short first-run fix cycle: run `black .`, run `pytest`, and fix any failures the
suite reports (most likely small assertion or message mismatches).
