# Deployment

> **Status: not deployed.** Deployment needs your hosting account, credentials and
> billing choices, none of which were available. All configuration is prepared; follow
> the steps below. Provider facts were checked against their official documentation in
> **November 2026** and can change; re-check before committing money or data.

## Hosting evaluation

HemoLink needs: a Python/Docker web host, **MySQL** (not SQLite), environment variables,
HTTPS, GitHub integration, and an automated deploy trigger.

| Option | Finding (Nov 2026) | Fit |
|---|---|---|
| **Render: web service (Docker)** | Supports Docker, managed HTTPS, custom domains, deploy hooks and env vars. **Free** web services spin down after 15 minutes idle, restart at any time, cannot attach disks. The **pre-deploy command requires a paid instance type.** Render offers no managed MySQL (free managed database is Postgres only, expiring after 30 days). | Good for the app; MySQL must be hosted elsewhere |
| **Aiven for MySQL** | **The free MySQL tier is being retired**: no new free services since 6 Nov 2026; remaining free services are powered off and deleted on 21 Dec 2026. The **Developer plan is about $5/month** (single node, 1 CPU, 1 GB RAM, always on). | Recommended real MySQL 8 option (paid) |
| **TiDB Cloud Starter** | Free tier, **MySQL-compatible** (not MySQL itself): up to five free instances, each with 5 GiB row storage and a monthly request-unit quota; scales to zero; public connections normally use TLS. | Free option; test compatibility (CHECK constraints, foreign keys) before relying on it |
| Railway, Fly.io, PythonAnywhere, cloud VMs | Not evaluated against current documentation for this report. | Possible alternatives; verify first |

### Recommendation

* **Best for a demonstration that must be real MySQL:** Render web service (free or
  Starter) + **Aiven for MySQL Developer** (~$5/month).
* **Zero-cost experiment:** Render free web service + **TiDB Cloud Starter**. Run the full
  test suite against it first (`TEST_DATABASE_URL`), and accept sleeping and cold starts.
  Do **not** replace MySQL with SQLite or Postgres to save money.

### Honest limitations

* A free Render web service sleeps after 15 minutes: the first request after a pause is
  slow, and the deploy smoke test allows for this.
* The in-memory rate limiter resets on restart and is per worker.
* There is no persistent disk and no file upload feature, so none is needed.
* Email needs an SMTP provider; without one, password reset is shown as unavailable.

## Step-by-step (owner actions)

### 1. Create the database

Create a MySQL 8 service (Aiven or TiDB), a database named `hemolink`, and a user with
rights on it. Note the host, port, user and password. Build the URL:

```
mysql+pymysql://USER:PASSWORD@HOST:PORT/hemolink?charset=utf8mb4
```
URL-encode special characters in the password. If your provider requires TLS (managed MySQL services usually do; check yours), the
Docker image's CA bundle is `/etc/ssl/certs/ca-certificates.crt`; set
`DB_SSL_CA` to it (on the web service and as the repository variable below).
Allow connections from the internet or from GitHub Actions runners and Render
(managed providers usually allow this by default; restrict by IP if you can).

### 2. Create the web service on Render

1. New → **Web Service** → connect the GitHub repository, branch `main`, **Language: Docker**.
2. Instance type: Free (demo) or Starter (always on).
3. Disable automatic deploys ("Auto-Deploy: Off") so that GitHub Actions controls releases.
4. Health check path: `/health/ready`.
5. Environment variables:

| Variable | Value |
|---|---|
| `APP_ENV` | `production` |
| `SECRET_KEY` | output of `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | the URL from step 1 |
| `DB_SSL_CA` | `/etc/ssl/certs/ca-certificates.crt` (if TLS is required) |
| `TRUST_PROXY_HOPS` | `1` |
| `PUBLIC_BASE_URL` | your public URL, e.g. `https://hemolink.onrender.com` |
| `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_FROM` | your SMTP provider (optional but needed for password reset) |
| `WEB_CONCURRENCY` | `2` (use `1` on a 512 MB instance if memory is tight) |

   Render sets `PORT` automatically and, to my knowledge, `RENDER_GIT_COMMIT` (confirm in
   Render's environment-variable documentation; if it is absent the smoke test simply skips
   the release check). Do **not** set
   `RUN_MIGRATIONS` or `ALLOW_DEMO_SEED` in production.
6. Copy the service's **Deploy Hook** URL (Settings → Deploy Hook). Treat it as a secret.

### 3. Configure GitHub

*Settings → Environments → New environment* named `production`; optionally add yourself
as a required reviewer. Add **environment secrets**: `PRODUCTION_DATABASE_URL` (same
value as `DATABASE_URL`) and `RENDER_DEPLOY_HOOK_URL`. Add **repository variables**:
`PRODUCTION_URL` and, if needed, `DB_SSL_CA`. Mark **CI result** as a required check on
`main`.

### 4. First release

Push to `main`. CI runs; when green, the Deploy workflow migrates the database, triggers
Render and smoke-tests the site. (Or run **Actions → Deploy → Run workflow** on `main`.)

### 5. Create the administrator

On the first deploy, create the admin using a one-off shell with the production
environment. On a paid Render instance use the Shell tab; otherwise run locally against
the production database:

```bash
DATABASE_URL='mysql+pymysql://...' DB_SSL_CA=/etc/ssl/certs/ca-certificates.crt \
APP_ENV=development FLASK_DEBUG=0 flask --app run create-admin
```
Enter the password at the prompt (or set `HEMOLINK_ADMIN_PASSWORD` for this one command
only). Never seed demo data into production: the command refuses when `APP_ENV` is
`production`.

## Migrations in production

* They run in the **migrate** job, before new code is requested, against a backed-up
  database. Take a backup first (check your provider's backup policy; otherwise use
  `mysqldump`).
* The initial migration only creates tables. Review every later migration for locks and
  data loss; avoid destructive changes in the same release as the code that stops using
  the data.
* To roll back a release: redeploy the previous commit from Render. Only downgrade the
  schema (`flask db downgrade`) deliberately, after checking the data impact.

## Production configuration summary

| Item | Setting |
|---|---|
| Server | Gunicorn (`--workers 2 --threads 4 --preload`), non-root container |
| HTTPS | Terminated by Render; the app trusts one proxy hop (`TRUST_PROXY_HOPS=1`), uses `Secure` cookies and sends HSTS |
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
