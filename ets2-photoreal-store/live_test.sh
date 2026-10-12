#!/usr/bin/env bash
# Live end-to-end test: boots the real Flask server, exercises routing,
# static files, and the key -> redeem -> download path over HTTP.
set -u
cd "$(dirname "$0")"

PORT=8199
TMP="$(mktemp -d)"
export DB_PATH="$TMP/live.db"
export PRODUCTS_DIR="$PWD/products"
export SITE_URL="http://127.0.0.1:$PORT"
export SECRET_KEY="live-test-secret"
export PAYPAL_CLIENT_ID="test_client_id"
export PAYPAL_SECRET="test_secret"
export SMTP_USER="x@y.z"; export SMTP_PASS="dummy"; export ADMIN_EMAIL="x@y.z"
export PORT="$PORT"

FAIL=0
check(){ if [ "$2" = "1" ]; then echo "  PASS  $1"; else echo "  FAIL  $1"; FAIL=$((FAIL+1)); fi; }

.venv/bin/python -m server.app >/tmp/live_server.log 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT

for i in $(seq 1 40); do
  curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1 && break
  sleep 0.25
done

echo "== server up =="
H="$(curl -s "http://127.0.0.1:$PORT/api/health")"
check "health returns ok" "$(echo "$H" | grep -c '"ok":true')"

echo "== routes & static =="
gt0(){ [ "$1" -ge 1 ] 2>/dev/null && echo 1 || echo 0; }   # normalise grep counts to 1/0
is200(){ [ "$1" = "200" ] && echo 1 || echo 0; }          # normalise http codes to 1/0
check "GET / serves page"   "$(gt0 "$(curl -s "http://127.0.0.1:$PORT/" | grep -c 'ETS2')")"
check "GET / serves css"    "$(is200 "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/styles.css")")"
check "GET / serves js"     "$(is200 "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/app.js")")"
check "GET /tos serves ToS" "$(gt0 "$(curl -s "http://127.0.0.1:$PORT/tos" | grep -c 'Terms of Service')")"
check "GET /api/config"     "$(gt0 "$(curl -s "http://127.0.0.1:$PORT/api/config" | grep -c 'paypal_client_id')")"
check "config has 14.81"    "$(gt0 "$(curl -s "http://127.0.0.1:$PORT/api/config" | grep -c '14.81')")"

echo "== purchase -> key -> redeem -> download =="
# Simulate the capture step by issuing a key straight to the DB (no PayPal).
RAW="$(DB_PATH="$DB_PATH" PRODUCTS_DIR="$PRODUCTS_DIR" .venv/bin/python - <<'PY'
import os
from server import db
db.init_db()
oid = db.create_order("premium", "live@example.com", "14.81")
print(db.issue_key("premium", oid))
PY
)"
echo "  issued key: $RAW"
URL="$(curl -s -X POST "http://127.0.0.1:$PORT/api/redeem" -H 'Content-Type: application/json' \
      -d "{\"key\":\"$RAW\"}" | .venv/bin/python -c 'import sys,json;print(json.load(sys.stdin).get("download_url",""))')"
check "redeem returned /dl/ url" "$(echo "$URL" | grep -c '/dl/')"

# download it and confirm it is a real zip (PK magic bytes)
MAGIC="$(curl -s "$URL" | head -c2 | od -An -c | tr -d ' \n')"
check "download is a ZIP (PK magic)" "$([ "$MAGIC" = "PK" ] && echo 1 || echo 0)"

# key is one-time
CODE2="$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:$PORT/api/redeem" \
        -H 'Content-Type: application/json' -d "{\"key\":\"$RAW\"}")"
check "re-redeem same key -> 409" "$([ "$CODE2" = "409" ] && echo 1 || echo 0)"

echo
if [ "$FAIL" -eq 0 ]; then echo "RESULT: OK (live end-to-end passed)"; else echo "RESULT: $FAIL FAILED"; exit 1; fi
