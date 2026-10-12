#!/usr/bin/env python3
"""
Offline smoke test for the storefront. No PayPal / SMTP needed - it exercises
the key -> redeem -> download path and the pricing config.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

tmp = tempfile.mkdtemp(prefix="storetest_")
os.environ["DB_PATH"] = os.path.join(tmp, "test.db")
os.environ["PRODUCTS_DIR"] = os.path.join(HERE, "products")
os.environ["SITE_URL"] = "http://test.local"
os.environ["SECRET_KEY"] = "test"
os.environ["TRUST_PROXY"] = "false"

from server import db, keys as keysgen  # noqa: E402
from server.app import app              # noqa: E402

db.init_db()
client = app.test_client()

fails = []


def check(name, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   {extra}" if extra else ""))
    if not cond:
        fails.append(name)


print("== /api/config pricing ==")
cfg = client.get("/api/config").get_json()
totals = {p["key"]: p["total"] for p in cfg["products"]}
check("standard total is 7.97 (6.99 + 14%)", totals.get("standard") == "7.97", str(totals))
check("premium total is 14.81 (12.99 + 14%)", totals.get("premium") == "14.81", str(totals))
check("no secret leaked in /api/config",
      "SECRET" not in client.get("/api/config").get_data(as_text=True).upper()
      and cfg.get("paypal_client_id") is not None)

print("== key format & hashing ==")
k = keysgen.generate_key()
check("generated key is 20 chars w/ dashes", len(k) == 23 and k.count("-") == 3, k)
check("normalise strips dashes", len(keysgen.normalise(k)) == 20)
check("valid format accepted", keysgen.is_valid_format(k))
check("lowercase + spaced input still valid", keysgen.is_valid_format("  " + k.lower().replace("-", " ") + " "))
check("bad char '1' rejected", not keysgen.is_valid_format("AAAAA-AAAAA-AAAAA-AAA1A"))
check("short key rejected", not keysgen.is_valid_format("ABC"))

print("== issue + redeem + download ==")
oid = db.create_order("premium", "buyer@example.com", "14.81")
raw = db.issue_key("premium", oid)

r = client.post("/api/redeem", json={"key": raw})
check("redeem returns 200", r.status_code == 200, str(r.status_code))
j = r.get_json()
check("redeem returns premium tier", j.get("tier") == "premium")
check("redeem returns a /dl/ url", (j.get("download_url") or "").startswith("http://test.local/dl/"))

token = j["download_url"].rsplit("/", 1)[-1]
d = client.get(f"/dl/{token}")
check("download returns 200", d.status_code == 200, str(d.status_code))
check("download is a zip attachment",
      "zip" in (d.headers.get("Content-Type") or "")
      and "ETS2_Photoreal_Premium.zip" in (d.headers.get("Content-Disposition") or ""))

r2 = client.post("/api/redeem", json={"key": raw})
check("second redeem of same key -> 409", r2.status_code == 409, str(r2.status_code))
check("409 message mentions already redeemed", "already" in (r2.get_json().get("error") or "").lower())

print("== error paths ==")
check("malformed key -> 400", client.post("/api/redeem", json={"key": "nope"}).status_code == 400)
check("unknown-but-valid key -> 404",
      client.post("/api/redeem", json={"key": keysgen.generate_key()}).status_code == 404)
check("bad token download -> 404", client.get("/dl/deadbeef").status_code == 404)
check("create-order bad email -> 400",
      client.post("/api/create-order", json={"tier": "premium", "email": "x"}).status_code == 400)
check("create-order unknown tier -> 400",
      client.post("/api/create-order", json={"tier": "gold", "email": "a@b.co"}).status_code == 400)
check("health -> 200 with counts", client.get("/api/health").status_code == 200)

print("== download cap ==")
oid2 = db.create_order("standard", "b2@example.com", "7.97")
raw2 = db.issue_key("standard", oid2)
tok = client.post("/api/redeem", json={"key": raw2}).get_json()["download_url"].rsplit("/", 1)[-1]
codes = [client.get(f"/dl/{tok}").status_code for _ in range(7)]
check("allows up to cap then blocks", codes[-1] in (429, 200) and 429 in codes, str(codes))

print()
if fails:
    print(f"RESULT: {len(fails)} FAILED -> {fails}")
    sys.exit(1)
print("RESULT: OK (all smoke checks passed)")
