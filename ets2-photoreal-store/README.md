# ETS2 Photorealism — Storefront

A self-hosted store that sells the **ETS2 Photorealism** ReShade preset pack.

* Static front page (about, showcase, buy, redeem, TikTok link, Terms).
* **PayPal-only** checkout, verified **server-side** before anything is delivered.
* After payment the buyer is **emailed a 20-character, one-time-use key**.
* Entering the key unlocks a download of the matching zip. The **files are theirs
  forever**; the **key works once**.
* A Terms page the buyer must agree to before checkout unlocks.

Everything runs on a single small Python service — no third-party store platform,
no monthly fees beyond your host.

---

## What's for sale

| Product | Contents | Default price (CAD) |
|--------|----------|---------------------|
| **Standard** | `ETS2_Photorealism.ini` + `ETS2_Photorealism_MAX.ini` + LUT + docs | $6.99 + 14% tax |
| **Premium**  | `ETS2_Premium.ini` + `ETS2_Premium_Depth.ini` + LUT + docs | $12.99 + 14% tax |

Prices and the tax rate live in `.env` and are **charged server-side**, so the
browser can never change what a customer pays.

> ⚠️ **Tax totals:** the totals are computed as `price × 1.14`. That gives
> **$7.97** (Standard) and **$14.81** (Premium). If you want the exact totals to
> be $7.99 / $14.18 instead, set `TOTAL_CAD_STANDARD` / `TOTAL_CAD_PREMIUM` in
> `.env` — those overrides win.

---

## How the money → key → download flow works

```
Browser                     Your server                    PayPal
   │                            │                            │
   │ 1. click "Buy"             │                            │
   │───────────────────────────>│                            │
   │                            │ 2. create order (amount    │
   │                            │    fixed HERE)             │
   │                            │───────────────────────────>│
   │<────── orderID ────────────│                            │
   │                            │                            │
   │ 3. buyer approves on PayPal                              │
   │────────────────────────────────────────────────────────>│
   │                            │                            │
   │ 4. POST /capture-order     │                            │
   │───────────────────────────>│ 5. capture + VERIFY        │
   │                            │    status == COMPLETED     │
   │                            │<──────────────────────────>│
   │                            │ 6. only NOW mint key,      │
   │                            │    email it to buyer       │
   │<────── key (once) ─────────│                            │
   │                            │                            │
   │ 7. POST /api/redeem  (one-time, atomic)                  │
   │───────────────────────────>│                            │
   │<───── short-lived /dl/ url │                            │
   │ 8. GET /dl/<token>  →  the zip                          │
```

The amount is set by **your server**, never the browser. A payment only counts
when **PayPal reports it COMPLETED** from a server-to-server call — a customer
merely landing back on your site is never trusted.

---

## Project layout

```
ets2-photoreal-store/
├── server/
│   ├── app.py          Flask app: routes, rate limiting, download serving
│   ├── config.py       loads .env; prices, PayPal, SMTP, paths
│   ├── db.py           SQLite: orders + keys (keys stored as hashes)
│   ├── keys.py         20-char key generation / hashing / validation
│   ├── paypal.py       PayPal REST v2: create / capture / inspect
│   ├── mailer.py       SMTP email that delivers the key
│   └── cli.py          admin: stats, orders, reissue a lost key
├── public/             the website (index, styles, app.js, tos)
├── products/           the zips actually served to buyers
├── build_products.py   rebuilds products/ from the preset source folder
├── smoke_test.py       offline test (no PayPal/SMTP needed)
├── live_test.sh        boots the server and tests the whole path over HTTP
├── THIRD_PARTY_NOTICES.md   shader licences + why we don't bundle .fx files
├── SETUP.md            full deploy guide (PayPal app, SMTP, gunicorn, going live)
└── .env.example        copy to .env and fill in
```

---

## Quick start (local)

```bash
cd ets2-photoreal-store
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then edit .env (see SETUP.md)
python build_products.py      # build the buyer zips
python -m server.app          # http://127.0.0.1:8000
```

Test it without spending money or sending real email:

```bash
python smoke_test.py     # offline unit-style checks
./live_test.sh           # real server + HTTP end-to-end
```

To try a purchase locally, put PayPal in **sandbox** mode and use a sandbox
buyer account, or just insert a key directly:

```bash
python - <<'PY'
from server import db
db.init_db()
oid = db.create_order("premium", "you@example.com", "14.81")
print("KEY:", db.issue_key("premium", oid))
PY
```

…then paste that key into the **Redeem** box on the site.

---

## Deploy it free (no hosting / domain cost)

To put the store online for **$0/month**, use the Oracle Cloud Always-Free tier +
a free DuckDNS subdomain. There's a one-command server setup script and a full
walkthrough in **`deploy/DEPLOY.md`** (`deploy/setup_server.sh` does the install,
HTTPS and service setup automatically).

You never need to buy a domain — DuckDNS gives you a free HTTPS address.

---

## Admin

```bash
python -m server.cli stats                 # paid orders, keys issued/redeemed
python -m server.cli orders                # recent orders
python -m server.cli reissue <order_id>    # buyer lost the email? mint a new key
```

Keys are stored **only as SHA-256 hashes**, so the original key can't be recovered
from the database — that's why `reissue` mints a *new* key for a paid order.

---

## Honest limitations (read this)

* **The key gates the download, not possession.** A `.ini` file that a buyer has
  on disk can be copied and shared like any text file. The one-time key system
  stops *casual* anonymous re-uploading (a stranger can't just grab a link), but
  it cannot stop a determined buyer who copies the files. No key system can. The
  Terms + the threat of enforcement are the real deterrent for that case.
* **These presets are tuning for third-party shaders.** Several shaders they drive
  are under "all rights reserved" / non-commercial licences. That's why the zips
  contain **only your own files** (presets, your LUT, your docs/script) and
  **no `.fx` shader code** — buyers install the shaders themselves from the
  official ReShade installer. Read `THIRD_PARTY_NOTICES.md` before you sell.
* **The Terms are a deterrent, not a guarantee.** They're a standard
  no-redistribution licence and are worth having, but enforcing them is a separate
  matter. Consider having a lawyer review them.

See `SETUP.md` to deploy, and `THIRD_PARTY_NOTICES.md` for the licensing detail.
