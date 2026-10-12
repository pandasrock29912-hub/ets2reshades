# Setup & deployment

End-to-end guide to taking real money. Read `README.md` first for the big picture.

---

## 0. Prerequisites

* Python **3.10+** (tested on 3.14).
* A server to run it on — any small VPS works (a $5–6/mo box with 1 GB RAM is
  plenty). You'll want a domain name, and HTTPS (free via Let's Encrypt / Caddy).
* A PayPal **Business** account.
* An email address you can send from (Gmail is easiest via an App Password).

---

## 1. Install

```bash
cd ets2-photoreal-store
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Configure

```bash
cp .env.example .env
```

Open `.env` and fill it in. Generate a secret key:

```bash
python3 -c "import secrets;print(secrets.token_hex(32))"
```

Key settings:

| Variable | What it does |
|----------|--------------|
| `SITE_URL` | The public URL (used in emails + PayPal redirects), e.g. `https://yourdomain.com` |
| `SECRET_KEY` | Random string from the command above |
| `PRICE_CAD_*`, `TAX_RATE` | Prices. Totals are `price × (1+TAX_RATE)` |
| `TOTAL_CAD_*` | Optional **exact** totals that override the computed ones |
| `PAYPAL_*` | From step 3 |
| `SMTP_*`, `ADMIN_EMAIL` | From step 4 |
| `TRUST_PROXY` | Set to `true` once you're behind a reverse proxy |

## 3. PayPal (developer app)

1. Go to <https://developer.paypal.com> → **Apps & Credentials**.
2. Toggle to **Sandbox** first. Create an application (or use the default one).
   Copy the **Client ID** and **Secret** into `.env` (`PAYPAL_CLIENT_ID`,
   `PAYPAL_SECRET`, `PAYPAL_ENV=sandbox`).
3. Test a purchase with a [sandbox buyer account](https://developer.paypal.com/developer/applications/)
   (PayPal gives you fake buyer logins).
4. When it works, switch the app to **Live**, copy the **live** Client ID and
   Secret, set `PAYPAL_ENV=live`, and redeploy.

Notes:
* The buttons request the **CAD** currency. Make sure your business account can
  accept CAD (most can; CAD is a supported PayPal currency).
* The **amount is set by your server** — the client can't tamper with it.
* Payments only count when PayPal reports the order `COMPLETED` server-side.

## 4. Email (send the key)

**Gmail** (simplest):
1. Enable **2-Step Verification** on the Google account.
2. Create an **App Password**: <https://myaccount.google.com/apppasswords>.
3. Put the 16-char app password in `SMTP_PASS`, your address in `SMTP_USER` and
   `MAIL_FROM`, and the same address in `ADMIN_EMAIL`.

Any SMTP provider works — just change `SMTP_HOST` / `SMTP_PORT`.

Every successful sale also emails **you** (`ADMIN_EMAIL`) a short sale note, and
if PayPal's verified payer email differs from what the buyer typed, the key is
sent to **both** so the real payer always gets it.

## 5. Build the product zips

```bash
python build_products.py
```

This reads the preset files from `../ETS2-Photoreal-Preset/` and writes
`products/ETS2_Photoreal_Standard.zip` and `products/ETS2_Photoreal_Premium.zip`.
**Re-run this whenever you tweak a preset** — the zips are what buyers download.

It refuses to include any `.fx`/`.fxh`/`.dll`/`.exe`, so you can't accidentally
redistribute third-party shader code (see `THIRD_PARTY_NOTICES.md`).

## 6. Run locally

```bash
python -m server.app          # http://127.0.0.1:8000
```

Test the whole path without PayPal/SMTP:

```bash
python smoke_test.py
./live_test.sh
```

## 7. Deploy (production)

Use **gunicorn** behind a reverse proxy. Example systemd unit
`/etc/systemd/system/ets2store.service`:

```ini
[Unit]
Description=ETS2 Photorealism store
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/ets2-photoreal-store
EnvironmentFile=/opt/ets2-photoreal-store/.env
ExecStart=/opt/ets2-photoreal-store/.venv/bin/gunicorn -w 2 -b 127.0.0.1:8000 server.app:app
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ets2store
```

Then put **Caddy** (or nginx) in front for HTTPS. With Caddy, one line is enough:

```
yourdomain.com {
    reverse_proxy 127.0.0.1:8000
}
```

Caddy auto-provisions Let's Encrypt certificates. **Set `TRUST_PROXY=true`** in
`.env` so rate-limiting sees real client IPs behind the proxy.

> The bundled Flask server is fine to run directly, but for real traffic use
> gunicorn (or any WSGI server) as shown — Flask's built-in server is not meant
> for production.

## 8. Admin tasks

```bash
python -m server.cli stats
python -m server.cli orders
python -m server.cli reissue <order_id> [email]   # buyer lost their key email
```

`reissue` mints a **new** key for an already-paid order (keys are stored hashed,
so the original can't be recovered). The old key, if the buyer still has it,
remains valid.

## 9. Going-live checklist

- [ ] `PAYPAL_ENV=live` with **live** Client ID + Secret
- [ ] `SITE_URL` is the real `https://…` domain (appears in emails + redirects)
- [ ] SMTP sends a real test email (do a sandbox→live test purchase)
- [ ] `TRUST_PROXY=true` behind the proxy
- [ ] `products/` zips are freshly built from your latest presets
- [ ] `.env` is **not** committed or public (`chmod 600 .env`)
- [ ] Terms reviewed (ideally by a lawyer)

## 10. Rebuilding after preset changes

```bash
cd ets2-photoreal-store
python build_products.py
sudo systemctl restart ets2store     # if already deployed
```

No other step needed — buyers always download the current `products/*.zip`.
