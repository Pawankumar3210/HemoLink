# Final project report

Legend: **Implemented** = code exists and was reviewed/statically verified.
**Tested** = covered by tests that were *written* (see `testing.md`; the database-backed
suite has not been executed yet). **Configured** = files exist but nothing was run.
**Deployed** = running publicly (nothing is deployed).

## Feature checklist

| Area | Feature | Implemented | Tests written |
|---|---|:-:|:-:|
| Accounts | Donor and recipient registration, validation, terms consent | Yes | Yes |
| Accounts | Login/logout, role redirects, generic errors, safe `next`, suspended handling | Yes | Yes |
| Accounts | Password hashing (scrypt), password reset (hashed, expiring, single-use tokens) | Yes | Yes |
| Accounts | Admin creation by CLI only; duplicate protection; no hard-coded password | Yes | Yes |
| Accounts | Account settings, password change, deletion with anonymisation | Yes | Yes |
| Donors | Profile create/edit, availability (3 states), search visibility, optional date sharing | Yes | Yes |
| Search | Blood group, state, city, availability, name, sorting, pagination, empty/loading states | Yes | Yes |
| Search | Hidden/suspended/deleted donors excluded; no phone/email exposure | Yes | Yes |
| Requests | Create, edit, cancel, fulfil, statuses, urgency, donor discovery list | Yes | Yes |
| Contact | Request, accept, decline, withdraw, revoke; consent timestamps; duplicate rules; atomic transitions | Yes | Yes |
| Notifications | Stored in MySQL; list, unread count, mark read/all; admin notices | Yes | Yes |
| Admin | Live statistics, users, donors, requests, contacts, audit log, system page, moderation | Yes | Yes |
| Security | RBAC, IDOR checks, CSRF, CSP and headers, rate limits, cookie flags, escaping | Yes | Yes |
| UI | 56 templates, one design system, responsive, accessible patterns, error pages | Yes | Template render checks executed |
| Reliability | `/health/live`, `/health/ready`, JSON logging, request ids | Yes | Yes |
| Data | 7 tables, constraints, indexes, hand-written migration matching the models | Yes | Cross-checked by script; CI runs it on MySQL |
| Demo | `seed-demo`: 24 donors across all 8 groups, 6 requests, 5 contacts, notifications | Yes | Yes |
| DevOps | Dockerfile (multi-stage, non-root, healthcheck), Compose (MySQL volume, health check, wait) | Configured | n/a (CI builds it) |
| DevOps | CI (lint, MySQL tests, migrations, coverage, Docker smoke test, audit) | Configured | n/a |
| DevOps | Deploy workflow (gate, migrate, hook, verify) | Configured | n/a |
| Docs | README, architecture, database (ER), pipeline (CI/CD diagram), deployment, testing, overview | Yes | n/a |

## Verified in the build environment (no network, Flask and Jinja2 only)

* All Python compiles; 61 endpoints cross-checked against every `url_for` call.
* All 56 templates compile; 80 renders of every page and many states succeeded.
* Rendered pages contain no inline scripts or styles (CSP-safe) and donor cards contain
  no contact details.
* 47 validation and utility test cases were executed and pass (one real bug found and
  fixed: tabs were being deleted by `clean_text`).
* Migration and models agree (0 differences in tables, columns, nullability, indexes,
  constraint names, foreign keys).
* Both workflows and Compose parse as YAML; shell scripts pass `sh -n`.

## Not yet verified (run these first)

1. `pip install -r requirements-dev.txt`, `black .`, `flake8 app tests scripts run.py`
2. `pytest` (SQLite), then `docker compose run --rm test` (MySQL)
3. `docker compose up --build`, create an admin, click through the app
4. Push to GitHub and watch CI; fix anything it reports

Likely first-run issues, honestly: small Black reformatting; a few test assertions that
need adjusting to exact text; `flask db check` may report a trivial drift (regenerate the
migration if so). None of these were observable without the real dependencies.

## Acceptance criteria

| Group | Status |
|---|---|
| Functional (registration, roles, profiles, search, requests, contact, notifications, admin) | Implemented; tests written; not executed |
| Technical (factory, blueprints, models, MySQL, migrations, env config, errors, security, no secrets in source) | Implemented. MySQL persistence and migrations are verified only structurally until CI runs |
| DevOps: Git structure, Dockerfile, Compose, Pytest, Flake8, Black, CI, deploy workflow, health checks, production config documented | Configured; **not executed** |
| DevOps: "failed checks block deployment" | Implemented in workflow logic (gate + `ci-success`); not demonstrated |
| Design (pages, validation, dashboards, desktop and mobile, accessibility) | Implemented; not viewed in a browser |
| Documentation (README, architecture, ER, CI/CD diagram, deployment) | Done; commands could not be executed to verify them |
| Public deployment | **Not done** (needs your accounts). Steps in `deployment.md` |

## Deployment status

Not deployed. Research (Nov 2026) changed the plan: Aiven's free MySQL is being retired,
Render has no MySQL and gates pre-deploy commands behind paid plans, so the design uses
Render for the app, an external MySQL (Aiven Developer ~$5/month, or TiDB Cloud Starter
free tier with compatibility caveats) and migrations as a gated workflow job.

## Known limitations

See README section 14. Notably: in-process rate limiting, self-reported eligibility, no
email verification, India-specific state list, dependency ranges rather than a lock
file, no screenshots.
