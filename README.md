# HemoLink

**Connecting Donors. Saving Lives.**

HemoLink is a blood donor registration and search portal. Donors register and choose
whether they can be found; recipients search by blood group and location and send a
short contact request; a donor's phone number is revealed only if that donor accepts.
Administrators moderate the platform. The project is built as an academic **DevOps**
project with automated tests, containers, CI/CD and a documented deployment path.

> HemoLink is an academic coordination project. It is **not** a blood bank, medical
> authority or emergency service, and it does not verify anyone's medical eligibility.

## Contents

1. [Overview and problem statement](#1-overview-and-problem-statement)
2. [Objectives and SDG 3](#2-objectives-and-sdg-3-alignment)
3. [Features and user roles](#3-features-and-user-roles)
4. [Technology stack and architecture](#4-technology-stack-and-architecture)
5. [Database overview](#5-database-overview)
6. [Screenshots](#6-screenshots)
7. [Local installation](#7-local-installation)
8. [Docker setup](#8-docker-setup)
9. [Testing and code quality](#9-testing-and-code-quality)
10. [Git workflow](#10-git-workflow)
11. [GitHub Actions and CI/CD](#11-github-actions-and-cicd)
12. [Deployment](#12-deployment)
13. [Security and privacy](#13-security-and-privacy)
14. [Known limitations](#14-known-limitations)
15. [Future enhancements and credits](#15-future-enhancements-and-credits)

## 1. Overview and problem statement

Finding a blood donor in a hurry usually means messaging friends, forwarding social
posts and calling around. Information is scattered and outdated, it is hard to know
who is willing and nearby, and nobody has an overview. HemoLink gives donors and
recipients one structured, searchable, consent-based place to find each other.

## 2. Objectives and SDG 3 alignment

Objectives: simple donor registration; organised donor profiles; blood-group and
location search; self-managed availability; blood requests; consent-based contact;
admin monitoring and moderation; privacy and security; and a complete, demonstrable
DevOps lifecycle.

**SDG 3 (Good Health and Well-being).** HemoLink supports the goal at a small scale
by making voluntary donors easier to discover and by reducing time lost to informal
coordination. It makes no claim to be an official health service (see the in-app SDG
page at `/sdg-3`).

## 3. Features and user roles

| Role | What they can do |
|---|---|
| **Donor** | Register, manage profile, set availability and search visibility, receive and accept/decline contact requests, end access after accepting, view open blood requests, notifications, account settings, delete account |
| **Recipient** | Register, search donors (blood group, state, city, availability, name, sorting, pagination), post/edit/cancel/fulfil blood requests, send contact requests, see donor phone only after acceptance, track requests, notifications |
| **Administrator** | Dashboard with live statistics, user/donor/request/contact management, suspend and reactivate accounts, reject requests with a reason, broadcast notices, audit log, system page |

All 39 pages and endpoints required by the specification exist (public, donor,
recipient, admin, error pages and `/health/live` and `/health/ready`).
Administrators are created only through the CLI; there is no public admin sign-up.

## 4. Technology stack and architecture

* **Frontend:** HTML5, CSS3, vanilla JavaScript, Jinja2 templates (no frontend framework).
* **Backend:** Python 3.12, Flask (application factory + blueprints), Flask-SQLAlchemy,
  Flask-Migrate, Flask-Login, Flask-WTF (CSRF), PyMySQL, Gunicorn.
* **Database:** MySQL 8 (SQLite is used only for fast local unit tests).
* **DevOps:** Git/GitHub, GitHub Actions, Docker, Docker Compose, Pytest + pytest-cov,
  Flake8, Black.

```
app/
  auth/ main/ donors/ blood_requests/ contact/ dashboard/ notifications/ admin/   # blueprints (routing)
  services/     # business logic and validation (no HTTP concerns)
  models/       # SQLAlchemy models
  templates/ static/
  utils/        # decorators, rate limiter, security helpers, logging
migrations/     # Alembic migrations
tests/          # pytest suite
scripts/        # container entrypoint, DB wait, healthcheck, smoke test
docs/           # architecture, database, pipeline, deployment, testing
.github/workflows/  ci.yml, deploy.yml
```

Layers: presentation (templates) → routing (blueprints) → services (business rules) →
models (SQLAlchemy) → MySQL. See [docs/architecture.md](docs/architecture.md).

## 5. Database overview

Seven tables: `users`, `donor_profiles`, `blood_requests`, `contact_requests`,
`notifications`, `audit_logs`, `password_reset_tokens`, with foreign keys, unique
constraints, CHECK constraints and indexes. The ER diagram and relationship
explanations are in [docs/database.md](docs/database.md).

## 6. Screenshots

Screenshots were not captured when this repository was generated, because the
application could not be run in the build environment. After starting the app,
add images to `docs/screenshots/` and reference them here:

```markdown
![Landing page](docs/screenshots/landing.png)
![Donor search](docs/screenshots/search.png)
![Admin dashboard](docs/screenshots/admin.png)
```

## 7. Local installation

**Requirements:** Python 3.12+, MySQL 8 (or Docker, see section 8), Git.

```bash
# 1. Environment
python -m venv .venv
source .venv/bin/activate            # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

# 2. Configuration
cp .env.example .env                 # then edit .env (see below)
python -c "import secrets; print(secrets.token_hex(32))"   # paste into SECRET_KEY
```

**MySQL setup** (one-time, as a MySQL admin user; choose your own password):

```sql
CREATE DATABASE hemolink      CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE hemolink_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'hemolink'@'localhost' IDENTIFIED BY 'a-strong-password';
GRANT ALL PRIVILEGES ON hemolink.*      TO 'hemolink'@'localhost';
GRANT ALL PRIVILEGES ON hemolink_test.* TO 'hemolink'@'localhost';
```

Set `DATABASE_URL` and `TEST_DATABASE_URL` in `.env` to match (the test database name
must contain `test`; the suite refuses to run otherwise because it drops tables).

```bash
# 3. Create the schema (Alembic migrations)
flask --app run db upgrade

# 4. Create your administrator (prompts for a password; never hard-coded)
flask --app run create-admin

# 5. Optional demo data (development only; random password is printed)
#    requires ALLOW_DEMO_SEED=true in .env
flask --app run seed-demo            # add --reset to recreate it

# 6. Run
flask --app run run --debug          # http://127.0.0.1:5000
```

Password-reset emails: leave `MAIL_SERVER` empty in development. The link is then
written to the server log and listed at `/dev/outbox` (development only; the page
returns 404 in production or whenever SMTP is configured).

Useful commands: `flask --app run db migrate -m "message"` (new migration),
`flask --app run db check` (models vs. migrations), `flask --app run purge-reset-tokens`.

## 8. Docker setup

```bash
cp .env.example .env     # set SECRET_KEY and URL-safe MYSQL_* passwords (letters/digits)
docker compose up --build            # app on http://localhost:8000, MySQL on a private network
docker compose exec web flask --app run create-admin
docker compose exec web flask --app run seed-demo       # optional demo data
docker compose logs -f web           # view logs
docker compose run --rm test         # run the test suite against MySQL (database hemolink_test)
docker compose down                  # stop; the MySQL volume (data) is kept
```

`docker compose down -v` also **deletes the database volume**; use it deliberately.
The MySQL service has a health check and the app waits for it (`scripts/wait_for_db.py`)
before starting. Migrations run at container start only when `RUN_MIGRATIONS=1`
(default in Compose). The `hemolink_test` database is created on first volume creation;
if you created the volume earlier, create it manually (see section 7).

## 9. Testing and code quality

```bash
black .                              # format once before your first commit
flake8 app tests scripts run.py
pytest --cov=app --cov-report=term-missing
```

Tests run on in-memory SQLite by default (`.env.example` leaves `TEST_DATABASE_URL`
unset). To run them on MySQL, set `TEST_DATABASE_URL` to a database whose name contains
`test`; set `TEST_USE_MIGRATIONS=1` to build the schema through the Alembic migrations.
`docker compose run --rm test` does both inside the container. The repository is
formatted with Black and passes `black --check` in CI. See
[docs/testing.md](docs/testing.md).

## 10. Git workflow

```bash
git init -b main
git add .
git commit -m "feat: add HemoLink application"      # or follow the commit plan below
git remote add origin https://github.com/<you>/HemoLink.git
git push -u origin main
```

Branches: `main` (stable, deployed), optional `develop`, `feature/*`, `fix/*`.
Commit style: `feat:`, `fix:`, `test:`, `ci:`, `docs:`. Suggested history:
`chore: project scaffold` → `feat: add models and migrations` → `feat: authentication
and roles` → `feat: donor profiles and search` → `feat: blood requests` →
`feat: consent-based contact workflow` → `feat: admin dashboard` → `test: add pytest
suite` → `ci: add GitHub Actions` → `feat: add Docker` → `docs: add documentation`.
Protect `main` (require the CI check) in the repository settings.

## 11. GitHub Actions and CI/CD

`.github/workflows/ci.yml` runs on pushes to `main`/`develop`, pull requests to `main`
and manual dispatch, with read-only permissions and no secrets:

1. **Lint and format**: Flake8 and `black --check`.
2. **Tests on MySQL** (needs lint): MySQL 8 service container; applies migrations,
   runs `flask db check`, downgrades and re-upgrades, then Pytest with coverage
   (fails below 80%). Uploads coverage and the exact resolved dependency versions.
3. **Dependency audit**: `pip-audit` (informational, does not block).
4. **Docker build and smoke test** (needs test): builds the images, starts the real
   stack with Compose and runs `scripts/smoke_test.sh`.
5. **CI result**: a single summary job that fails unless every required check passed.

`.github/workflows/deploy.yml` runs only after CI succeeds on a push to `main`
(or by manual dispatch on `main`): migrate the production database (in the
`production` environment, optionally requiring approval) → trigger the Render deploy
hook → smoke-test the live URL and confirm the new release id is serving.
Diagrams and details: [docs/devops-pipeline.md](docs/devops-pipeline.md).

## 12. Deployment

Chosen arrangement (verified against provider documentation in November 2026):
**Render** Docker web service + an external **managed MySQL 8** database.
Costs and limits, step-by-step instructions, GitHub secrets, backups and the owner's
verification checklist are in [docs/deployment.md](docs/deployment.md). **The
application has not been deployed**: that needs your hosting account, credentials and
billing decisions. Everything else is prepared.

## 13. Security and privacy

Server-side role checks on every protected endpoint (plus an admin blueprint guard);
object-level ownership checks (IDOR-safe); CSRF protection; hashed passwords (Werkzeug
scrypt); strict input validation with controlled vocabularies; parameterised SQL via
the ORM with LIKE-wildcard escaping; auto-escaped templates and a strict Content
Security Policy (no inline scripts/styles); secure, HttpOnly, SameSite cookies;
rate limiting on login, registration, password reset and contact requests;
time-limited single-use reset tokens stored only as hashes; no phone/email in search
or public pages; consent timestamps; account deletion that anonymises personal data;
audit log for admin actions; JSON logs without personal details in production.
See [docs/architecture.md](docs/architecture.md#security-design).

## 14. Known limitations

* The rate limiter is in-process (per Gunicorn worker); use a shared store such as
  Redis if you scale to multiple instances.
* Availability and eligibility are self-reported; there is no donor verification.
* Email is plain SMTP with no queue; there is no email verification yet.
* The state list is India-specific; city is free text.
* Free hosting tiers sleep when idle and free MySQL options are limited (see deployment doc).
* Dependencies are constrained to compatible ranges, not locked to exact versions.

## 15. Future enhancements and credits

Email/SMS notifications, email verification, donor verification, hospital partnerships,
map-based and distance search, analytics and exports, multi-language UI, PWA support.

Credits: built as an academic DevOps project supporting UN SDG 3. Fonts: Public Sans and
Newsreader (Google Fonts, SIL Open Font License).
