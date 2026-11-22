# Project overview (for the academic report)

## Title

**HemoLink: Blood Donor Registration and Search Portal.** Connecting Donors. Saving Lives.

## Problem statement

People who need blood urgently rely on personal contacts, social media and informal
lists. This causes delayed discovery, fragmented and outdated information, difficulty
finding a donor of a specific blood group nearby, no visibility of availability, and no
central oversight.

## Objectives

1. Simple donor registration and organised profiles.
2. Recipient search by blood group, location and availability.
3. Donor-controlled availability and search visibility.
4. Blood requests with statuses.
5. Consent-based donor-recipient contact (no public phone numbers).
6. Administrator monitoring, moderation and an audit trail.
7. Security and privacy by design.
8. A complete DevOps lifecycle: version control, automated quality gates, containers,
   CI/CD and deployment preparation.

## SDG 3 alignment

HemoLink supports **Sustainable Development Goal 3: Good Health and Well-being** by
helping voluntary donors and people who need blood find each other faster and with respect
for consent. It is a coordination aid, not a healthcare institution, and it never claims
to verify medical eligibility.

## Scope

In scope: registration and roles, donor profiles, search, blood requests, contact
workflow, notifications, admin console, tests, Docker, CI/CD, documentation.
Out of scope: medical eligibility checks, payments, maps, SMS, native apps, file uploads.

## Technology decisions

| Decision | Reason |
|---|---|
| Flask + Jinja, no SPA | Matches the brief; simple to explain and test; server-side authorisation |
| MySQL 8 + SQLAlchemy + Alembic | Required by the brief; constraints enforce data rules; versioned schema |
| Services layer | Keeps business rules testable and out of the HTTP layer |
| In-process rate limiter | No extra infrastructure for a student project; limitation documented |
| Consent via accept/decline | Privacy: donors choose; recipients see a phone only after consent |
| Migrations as a gated CI step | Render's pre-deploy command is paid-only; avoids migrating on every start |
| Compose with a separate test database | Tests cannot touch application data |

## DevOps lifecycle demonstrated

Plan → code (Git branches, conventional commits) → build (Docker multi-stage image) →
test (Pytest on MySQL, coverage gate) → quality (Flake8, Black, pip-audit) → release
(GitHub Actions) → deploy (gated migration, Render deploy hook) → operate (health
checks, JSON logs, smoke tests). See `devops-pipeline.md`.

## Limitations and future work

See the README sections "Known limitations" and "Future enhancements".
