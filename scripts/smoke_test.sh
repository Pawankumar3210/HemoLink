#!/bin/sh
# Post-deployment smoke test.
#   scripts/smoke_test.sh https://your-app.example.com [expected-release-prefix]
# Waits for the app to be ready (and, if given, for the expected release to be live),
# then checks public pages, static assets, authorization and HTTPS headers.
set -eu

BASE="${1:?usage: smoke_test.sh BASE_URL [EXPECTED_RELEASE]}"
BASE="${BASE%/}"
EXPECTED="${2:-}"
ATTEMPTS="${SMOKE_ATTEMPTS:-40}"
DELAY="${SMOKE_DELAY:-15}"

fail() { echo "FAIL: $1" >&2; exit 1; }
ok() { echo "ok:   $1"; }

status_of() { curl -s -o /dev/null -w "%{http_code}" --max-time 20 "$@"; }

echo "Waiting for $BASE to become ready (up to $ATTEMPTS attempts)..."
i=0
until [ "$(status_of "$BASE/health/ready")" = "200" ]; do
    i=$((i + 1))
    [ "$i" -ge "$ATTEMPTS" ] && fail "service did not become ready"
    sleep "$DELAY"
done
ok "readiness endpoint reports ready (database reachable)"

if [ -n "$EXPECTED" ]; then
    SHORT=$(printf '%s' "$EXPECTED" | cut -c1-7)
    i=0
    while :; do
        BODY=$(curl -fsS --max-time 20 "$BASE/health/live" || true)
        case "$BODY" in
            *'"release"'*)
                if printf '%s' "$BODY" | grep -Eq "\"release\": ?\"$SHORT"; then
                    ok "release $SHORT is live"
                    break
                fi
                ;;
            *)
                echo "note: the app does not report a release id; skipping release check"
                break
                ;;
        esac
        i=$((i + 1))
        [ "$i" -ge "$ATTEMPTS" ] && fail "expected release $SHORT never became live"
        sleep "$DELAY"
    done
fi

[ "$(status_of "$BASE/health/live")" = "200" ] || fail "liveness"
ok "liveness endpoint"

BODY=$(curl -fsS --max-time 20 "$BASE/") || fail "landing page"
case "$BODY" in *HemoLink*) ok "landing page";; *) fail "landing page content";; esac

[ "$(status_of "$BASE/login")" = "200" ] || fail "login page"
ok "login page"
[ "$(status_of "$BASE/register/donor")" = "200" ] || fail "registration page"
ok "registration page"
[ "$(status_of "$BASE/static/css/main.css")" = "200" ] || fail "static assets"
ok "static assets"

# Authorization: protected pages must redirect anonymous visitors to the login page.
for path in /admin/ /donors/search /dashboard /requests/; do
    code=$(status_of "$BASE$path")
    [ "$code" = "302" ] || fail "$path returned $code for an anonymous visitor (expected 302)"
done
ok "protected pages redirect anonymous visitors"

HEADERS=$(curl -sI --max-time 20 "$BASE/")
printf '%s' "$HEADERS" | grep -qi "^content-security-policy:" || fail "CSP header missing"
ok "security headers present"

case "$BASE" in
    https://*)
        if printf '%s' "$HEADERS" | grep -qi "^strict-transport-security:"; then
            ok "served over HTTPS with HSTS"
        else
            echo "warning: HSTS header missing; check TRUST_PROXY_HOPS=1 on the host"
        fi
        ;;
    *) echo "note: not HTTPS (local run); skipping HSTS check" ;;
esac

echo "Smoke test passed for $BASE"
