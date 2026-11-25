# Database

MySQL 8 (utf8mb4). Schema changes are managed with Alembic through Flask-Migrate; the
initial migration is `migrations/versions/7c1f2a9d4b10_initial_schema.py`.
Constraint names follow a fixed naming convention (`app/extensions.py`) so migrations
stay stable. Controlled vocabularies are enforced with CHECK constraints (enforced by
MySQL 8.0.16+).

## Entity relationship diagram

Core columns are shown below; `created_at` / `updated_at` audit timestamps are omitted from
some entities for readability but are present in the migration and models.

```mermaid
erDiagram
    USERS ||--o| DONOR_PROFILES : "has (donors only)"
    USERS ||--o{ BLOOD_REQUESTS : "posts (recipients)"
    USERS ||--o{ CONTACT_REQUESTS : "receives as donor"
    USERS ||--o{ CONTACT_REQUESTS : "sends as recipient"
    BLOOD_REQUESTS |o--o{ CONTACT_REQUESTS : "optionally linked"
    USERS ||--o{ NOTIFICATIONS : "receives"
    USERS ||--o{ AUDIT_LOGS : "performs"
    USERS ||--o{ PASSWORD_RESET_TOKENS : "requests"

    USERS {
        int id PK
        string full_name
        string email UK
        string phone
        string password_hash
        string role "donor|recipient|admin"
        string account_status "active|suspended|deleted"
        datetime created_at
        datetime updated_at
        datetime last_login_at
    }
    DONOR_PROFILES {
        int id PK
        int user_id FK,UK
        string blood_group "A+..O-"
        int age "18-65"
        string gender
        string state
        string city
        date last_donation_date
        string availability_status
        bool visible_in_search
        bool share_last_donation_date
    }
    BLOOD_REQUESTS {
        int id PK
        int requester_id FK
        string blood_group
        int units_required "1-20"
        string hospital_name
        string state
        string city
        date required_by
        string urgency "normal|high|urgent"
        string status "open|fulfilled|cancelled|rejected"
        string notes
        string moderation_note
        datetime status_changed_at
    }
    CONTACT_REQUESTS {
        int id PK
        int donor_id FK
        int recipient_id FK
        int blood_request_id FK "nullable"
        string message
        string status "pending|accepted|declined|withdrawn"
        datetime donor_consent_at
        datetime recipient_access_revoked_at
        datetime responded_at
    }
    NOTIFICATIONS {
        int id PK
        int user_id FK
        string title
        string message
        string related_type
        int related_id
        bool is_read
        datetime created_at
    }
    AUDIT_LOGS {
        int id PK
        int actor_id FK "nullable"
        string action
        string entity_type
        int entity_id
        string details
        datetime created_at
    }
    PASSWORD_RESET_TOKENS {
        int id PK
        int user_id FK
        string token_hash UK "sha-256"
        datetime expires_at
        datetime used_at
    }
```

## Relationships and deletion behaviour

* `users` 1-to-0..1 `donor_profiles` (unique `user_id`, `ON DELETE CASCADE`).
* `users` 1-to-many `blood_requests`, `notifications`, `password_reset_tokens`
  (`ON DELETE CASCADE`).
* `contact_requests` link two users: `donor_id` and `recipient_id` (both cascade) and
  optionally a blood request (`ON DELETE SET NULL`).
* `audit_logs.actor_id` is `ON DELETE SET NULL` so the audit trail survives user removal.
* The application never hard-deletes users in normal operation: deletion anonymises
  (see architecture). Cascades matter only for the demo-data reset command.

## Indexes and constraints

| Table | Notable indexes / constraints | Why |
|---|---|---|
| users | unique `email`; `(role, account_status)`; `created_at`; CHECKs on role and status | login lookup, admin filters |
| donor_profiles | `(visible_in_search, blood_group, state, city)`; `availability_status`; CHECKs on blood group, availability, age | the donor search query |
| blood_requests | `(requester_id, status)`; `(status, blood_group, state, city)`; `created_at`; CHECKs on group, urgency, status, units | "my requests" and donor discovery |
| contact_requests | `(donor_id, recipient_id, blood_request_id)`; `(donor_id, status)`; `(recipient_id, status)`; CHECK on status | duplicate checks and inbox queries |
| notifications | `(user_id, is_read, created_at)` | unread counts and lists |
| audit_logs | `created_at`; `(actor_id, created_at)`; `(entity_type, entity_id)` | admin log browsing |
| password_reset_tokens | unique `token_hash`; `user_id` | token lookup |

The "no duplicate active contact request for the same purpose" rule depends on NULL
handling (`blood_request_id` is nullable), which a MySQL unique index cannot express, so
it is enforced in `services/contacts.py` and covered by tests.

## Search query

Search is a single SQL query (no client-side filtering): joins `donor_profiles` to
`users`, requires `visible_in_search`, an active account and the donor role, applies the
optional filters (case-insensitive prefix match for city, substring for name, with LIKE
wildcards escaped), orders by availability then name, and paginates in the database.
Sorting by last donation date is deliberately not offered because it would leak the date
of donors who chose not to share it.

## Migrations

```bash
flask --app run db upgrade      # apply
flask --app run db downgrade base
flask --app run db migrate -m "describe change"   # generate after changing models
flask --app run db check        # fails if models and migrations differ
```

The initial migration was written by hand and cross-checked against the models
programmatically (tables, columns, nullability, indexes, constraint names and foreign
keys matched). CI also runs `db upgrade`, `db check`, `db downgrade base` and
`db upgrade` against MySQL. If `db check` reports a difference on first run, regenerate
with `flask db migrate` and review the result.

## Backups

Take a backup before every production migration (see `deployment.md`). Locally:

```bash
docker compose exec db sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"' > backup.sql
```
