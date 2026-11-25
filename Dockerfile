# syntax=docker/dockerfile:1

# ---- builder: compile dependency wheels (keeps build tooling out of the runtime) ----
FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY requirements.txt .
RUN pip wheel --wheel-dir /wheels -r requirements.txt

# ---- runtime: small, non-root, production image ----
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    APP_ENV=production \
    PORT=8000
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin hemolink
WORKDIR /app
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-index --find-links=/wheels -r requirements.txt && rm -rf /wheels
COPY --chown=hemolink:hemolink . .
RUN chmod +x scripts/entrypoint.sh
USER hemolink
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "scripts/healthcheck.py"]
ENTRYPOINT ["scripts/entrypoint.sh"]

# ---- dev: runtime plus test and lint tools (used by `docker compose run test`) ----
FROM runtime AS dev
USER root
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt && chown -R hemolink:hemolink /app
USER hemolink

# The last stage is the default build target, so make production the default.
FROM runtime AS production
