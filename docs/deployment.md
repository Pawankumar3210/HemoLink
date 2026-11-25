# Deployment

> **Status: not deployed.** Deployment needs your hosting account, credentials and
> billing choices, none of which were available. All configuration is prepared; follow
> the steps below. Provider facts were checked against their official documentation in
> **November 2026** and can change; re-check before committing money or data.

## Hosting evaluation

HemoLink needs: a Python web host, **MySQL** (not SQLite), environment variables,
HTTPS, GitHub integration, and an automated deploy trigger.

| Option | Finding (Nov 2026) | Fit |
|---|---|---|
| **Vercel (Python serverless)** | Supports Python serverless functions, managed HTTPS, env vars, and GitHub deploys. Flask apps can run through a WSGI entrypoint. Serverless instances are ephemeral/cold-started and may run concurrently, so DB connections and in-memory state must be handled carefully. | Works with repo config added here; use external MySQL with pooling/TLS |
| **Render: web service (Docker)** | Supports Docker, managed HTTPS, custom domains, deploy hooks and env vars. **Free** web services spin down after 15 minutes idle, restart at any time, cannot attach disks. The **pre-deploy command requires a paid instance type.** Render offers no managed MySQL (free managed database is Postgres only, expiring after 30 days). | Good for long-running app; MySQL must be hosted elsewhere |
| **Aiven for MySQL** | **The free MySQL tier is being retired**: no new free services since 6 Nov 2026; remaining free services are powered off and deleted on 21 Dec 2026. The **Developer plan is about $5/month** (single node, 1 CPU, 1 GB RAM, always on). | Recommended real MySQL 8 option (paid) |
| **TiDB Cloud Starter** | Free tier, **MySQL-compatible** (not MySQL itself): up to five free instances, each with 5 GiB row storage and a monthly request-unit quota; scales to zero; public connections normally use TLS. | Free option; test compatibility (CHECK constraints, foreign keys) before relying on it |
| Railway, Fly.io, PythonAnywhere, cloud VMs | Not evaluated against current documentation for this report. | Possible alternatives; verify first |

### Recommendation

* **If you want Vercel:** Vercel + managed MySQL (Aiven/TiDB/PlanetScale-compatible MySQL service). This repo now includes `vercel.json` and `api/index.py`.
* **Best for a long-running demonstration with real MySQL:** Render web service (free or Starter) + **Aiven for MySQL Developer** (~$5/month).
* **Zero-cost experiment:** Vercel or Render free tier + **TiDB Cloud Starter**. Run the full test suite against it first (`TEST_DATABASE_URL`).
* Do **not** replace MySQL with SQLite or Postgres to save money.

### Honest limitations

* Vercel serverless functions are ephemeral/cold-started. The in-memory rate limiter resets per instance/cold start and is not globally shared.
* MySQL must be externally hosted and reachable from Vercel. Use TLS as required by your provider; the app enables SSL CA auto-detection on Vercel when possible.
* On Vercel, SQLAlchemy uses `NullPool` to avoid stale pooled connections across serverless invocations. For production traffic, use a MySQL provider/proxy designed for serverless connection limits.
* There is no persistent disk and no file upload feature, so none is needed.
* Email needs an SMTP provider; without one, password reset is shown as unavailable.

## Vercel deployment (owner actions)

### 1. Create the database

Create a MySQL 8 / MySQL-compatible service (Aiven, TiDB, or another managed MySQL),
a database named `hemolink`, and a user with rights on it. Build the URL:

```
mysql+pymysql://USER:PASSWORD@HOST:PORT/hemolink?charset=utf8mb4
```

URL-encode special characters in the password. If your provider requires TLS, set
`DB_SSL_CA` to a CA bundle path available in the runtime, or rely on Vercel's standard
CA paths (the app auto-detects common locations). Confirm the DB allows connections
from Vercel.

### 2. Import project in Vercel

1. Vercel Dashboard → **Add New Project** → import the GitHub repo.
2. Framework preset: **Other** (or let Vercel detect Python). Root directory: repo root.
3. Build/install is handled by `vercel.json` + `@vercel/python`; `requirements.txt` is used.
4. Set environment variables (Production/Preview as needed):

| Variable | Value |
|---|---|
| `APP_ENV` | `production` |
| `SECRET_KEY` | output of `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | MySQL URL from step 1 |
| `DB_SSL_CA` | optional CA path if your provider requires a specific cert |
| `TRUST_PROXY_HOPS` | `1` (recommended on Vercel) |
| `PUBLIC_BASE_URL` | `https://your-project.vercel.app` (or custom domain) |
| `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_FROM` | optional SMTP for password reset |
| `RATELIMIT_ENABLED` | `1` (in-memory, per instance) |

Do **not** set `ALLOW_DEMO_SEED` in production.

### 3. Run migrations before/after first deploy

Vercel does not run Flask migrations automatically. Run once from a trusted machine/CI
with production env vars:

```bash
DATABASE_URL='mysql+pymysql://...' SECRET_KEY='...' APP_ENV=production \
flask --app run db upgrade
```

### 4. Create admin

```bash
DATABASE_URL='mysql+pymysql://...' SECRET_KEY='...' APP_ENV=development FLASK_DEBUG=0 \
flask --app run create-admin
```

### 5. Verify

- Visit `/health/live` and `/health/ready`
- Register/login, donor search, requests, contact flow
- Confirm static CSS/JS load and animations work
- Confirm HTTPS and secure cookies

## Render/Docker deployment (alternative)

The previous Render + Docker path remains supported by `Dockerfile`, `docker-compose.yml`,
`scripts/entrypoint.sh`, and CI workflows. Use it if you want a long-running container
instead of Vercel serverless.

## Migrations in production

* Run migrations against a backed-up database before exposing new code.
* For Render/Docker CI, the deploy workflow runs them in a gated step. For Vercel, run
  `flask --app run db upgrade` manually/CI with production env vars.
* The initial migration only creates tables. Review every later migration for locks and
  data loss; avoid destructive changes in the same release as the code that stops using
  the data.
* Roll back by redeploying the previous commit. Only downgrade the schema
  (`flask db downgrade`) deliberately, after checking the data impact.

## Production configuration summary

| Item | Setting |
|---|---|
| Vercel | Python serverless via `api/index.py` + `vercel.json`; app sets `TRUST_PROXY_HOPS=1` on Vercel by default; uses `NullPool` for SQLAlchemy on serverless |
| Docker/Render | Gunicorn (`--workers 2 --threads 4 --preload`), non-root container |
| HTTPS | Terminated by platform; app should trust proxy hops as configured, uses `Secure` cookies and sends HSTS in production |
| Secrets | Environment variables only; the app refuses to start with a missing or weak `SECRET_KEY` |
| Logging | JSON to stdout (`LOG_JSON` defaults to on in production) |
| Health | `/health/live`, `/health/ready` |
| Errors | Generic 4xx/5xx pages, no stack traces |

## Owner's post-deployment checklist

The automated smoke test covers the landing page, readiness (database connectivity),
login and registration pages, static assets, anonymous-access redirects, security
headers and HTTPS. Verify the rest by hand once:

- [ ] Register a donor and a recipient (use two browsers)
- [ ] Donor profile saved and visible in search; search by blood group and city works
- [ ] Recipient posts a blood request; sends a contact request; donor accepts; phone appears
- [ ] Admin signs in; dashboard numbers match; suspend/reactivate a test user
- [ ] A non-admin gets 403 on `/admin/`
- [ ] Password reset email arrives (if SMTP configured)
- [ ] HTTPS padlock, no mixed-content warnings, fonts load
- [ ] Phone view at ~375 px width: navigation and tables usable
