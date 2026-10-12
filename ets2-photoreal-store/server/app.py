"""
ETS2 Photorealism storefront.

Endpoints
  GET  /api/config          public prices + PayPal client id (no secrets)
  POST /api/create-order    server fixes the amount, creates a PayPal order
  POST /api/capture-order   captures + VERIFIES with PayPal, then issues a key
  POST /api/redeem          one-time key redemption -> short-lived download url
  GET  /dl/<token>          serves the zip bound to a redeemed key
  GET  /api/health          liveness probe
  GET  /tos                 terms of service page

Security posture
  * Amounts are computed server-side; the browser cannot change what is charged.
  * A payment only counts when PayPal reports the order COMPLETED from a
    server-to-server call. A client redirect is never trusted.
  * Keys are stored only as SHA-256 hashes; the raw key exists once, in email.
  * Redemption is an atomic UPDATE ... WHERE used_at IS NULL (one-time, race-safe).
  * Redeem and create-order are rate-limited per IP.
"""
import os
import re
import time
from collections import defaultdict, deque
from threading import Lock

from flask import Flask, jsonify, request, send_file, send_from_directory

from . import config, db, keys as keysgen, mailer, paypal

PUBLIC_DIR = os.path.join(config.ROOT, "public")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")

app = Flask(__name__, static_folder=PUBLIC_DIR, static_url_path="")

# --- tiny per-IP rate limiter ------------------------------------------------
class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, window: int = 3600) -> bool:
        t = time.time()
        with self._lock:
            q = self._hits[key]
            while q and q[0] < t - window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(t)
            return True


_limiter = RateLimiter()


def _client_ip() -> str:
    if config.env_bool("TRUST_PROXY", False):
        fwd = request.headers.get("X-Forwarded-For", "")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _rate_ok(bucket: str, limit: int) -> bool:
    return _limiter.allow(f"{bucket}:{_client_ip()}", limit)


# --- pages -------------------------------------------------------------------
@app.get("/")
def index():
    return send_from_directory(PUBLIC_DIR, "index.html")


@app.get("/tos")
def tos():
    return send_from_directory(PUBLIC_DIR, "tos.html")


# --- public config -----------------------------------------------------------
@app.get("/api/config")
def api_config():
    products = [
        {
            "key": p["key"],
            "name": p["name"],
            "badge": p["badge"],
            "blurb": p["blurb"],
            "price": f'{p["price"]:.2f}',
            "tax_rate": config.TAX_RATE,
            "total": f'{p["total"]:.2f}',
            "currency": config.CURRENCY,
        }
        for p in config.PRODUCTS.values()
    ]
    return jsonify(
        {
            "site": config.SITE_NAME,
            "currency": config.CURRENCY,
            "tax_rate": config.TAX_RATE,
            "paypal_client_id": config.PAYPAL_CLIENT_ID,
            "paypal_env": config.PAYPAL_ENV,
            "products": products,
        }
    )


# --- checkout ---------------------------------------------------------------
@app.post("/api/create-order")
def api_create_order():
    if not _rate_ok("create", config.ORDER_RATE_LIMIT):
        return jsonify({"error": "Too many attempts. Please wait a bit."}), 429

    body = request.get_json(silent=True) or {}
    tier = (body.get("tier") or "").strip().lower()
    email = (body.get("email") or "").strip()

    if tier not in config.PRODUCTS:
        return jsonify({"error": "Unknown product."}), 400
    if not EMAIL_RE.match(email):
        return jsonify({"error": "Enter a valid email address - your key is sent there."}), 400
    if not config.PAYPAL_CLIENT_ID or not config.PAYPAL_SECRET:
        return jsonify({"error": "Payments are not configured on the server yet."}), 503

    product = config.PRODUCTS[tier]
    amount = f'{product["total"]:.2f}'

    # record intent first so we always have the buyer's email for this payment
    order_id = db.create_order(tier, email, amount)

    try:
        paypal_order_id = paypal.create_order(
            amount=amount,
            tier=tier,
            our_order_id=order_id,
            return_url=f"{config.SITE_URL}/?paypal=return",
            cancel_url=f"{config.SITE_URL}/?paypal=cancel",
        )
    except paypal.PayPalError as exc:
        app.logger.error("PayPal create_order error: %s", exc)
        db.set_order_status(order_id, "failed")
        return jsonify({"error": "Could not start checkout with PayPal. Try again shortly."}), 502

    db.attach_paypal_order(order_id, paypal_order_id)
    return jsonify({"orderID": paypal_order_id, "amount": amount, "currency": config.CURRENCY})


@app.post("/api/capture-order")
def api_capture_order():
    if not _rate_ok("capture", config.ORDER_RATE_LIMIT):
        return jsonify({"error": "Too many attempts. Please wait a bit."}), 429

    body = request.get_json(silent=True) or {}
    paypal_order_id = (body.get("orderID") or "").strip()
    if not paypal_order_id:
        return jsonify({"error": "Missing order id."}), 400

    order = db.get_order_by_paypal(paypal_order_id)
    if not order:
        return jsonify({"error": "Order not found."}), 404
    if order["status"] == "paid":
        # Idempotent: never mint a second key for one payment.
        return jsonify({"already_paid": True, "message": "This order was already completed."})

    try:
        capture = paypal.capture_order(paypal_order_id)
    except paypal.PayPalError as exc:
        app.logger.error("PayPal capture error: %s", exc)
        return jsonify({"error": "PayPal did not confirm the payment. Nothing was charged twice."}), 502

    if not paypal.is_completed(capture):
        return jsonify({"error": "Payment not completed yet. If you were charged, contact support."}), 409

    # Money cleared -> fetch authoritative payer details and issue the key.
    payer_email = ""
    try:
        payer_email = paypal.payer_email(paypal.get_order(paypal_order_id))
    except paypal.PayPalError:
        pass

    tier = order["tier"]
    raw_key = db.issue_key(tier, order["id"])
    db.set_order_status(order["id"], "paid", payer_email or None)

    # Primary delivery: the email the buyer typed. Fallback: PayPal's verified
    # payer email, so the actual payer always receives the key.
    sent_ok = False
    recipients = []
    if order["email"]:
        recipients.append(order["email"])
    if payer_email and payer_email.lower() != (order["email"] or "").lower():
        recipients.append(payer_email)
    for to in recipients:
        try:
            mailer.send_key(to, raw_key, tier)
            sent_ok = True
        except Exception as exc:  # noqa: BLE001 - report but don't strand the buyer
            app.logger.error("Failed to email key to %s: %s", to, exc)

    mailer.notify_admin(
        f"sale: {tier} ${order['amount']} {config.CURRENCY}",
        f"order={order['id']}\npaypal={paypal_order_id}\nbuyer={order['email']}\n"
        f"payer_email={payer_email}\namount={order['amount']} {config.CURRENCY}\n"
        f"key_sent={'yes' if sent_ok else 'NO (see logs)'}",
    )

    return jsonify(
        {
            "ok": True,
            "key": raw_key,          # shown once on the confirmation screen
            "tier": tier,
            "email_sent": sent_ok,
            "emails": recipients,
        }
    )


# --- redemption -------------------------------------------------------------
@app.post("/api/redeem")
def api_redeem():
    if not _rate_ok("redeem", config.REDEEM_RATE_LIMIT):
        return jsonify({"error": "Too many attempts. Please wait an hour."}), 429

    body = request.get_json(silent=True) or {}
    raw = body.get("key") or ""
    if not keysgen.is_valid_format(raw):
        return jsonify({"error": "Keys are 20 characters (letters and numbers, no O/0/I/1)."}), 400

    row = db.claim_key(raw)
    if row is None:
        if db.key_already_used(raw):
            return jsonify({"error": "This key has already been redeemed."}), 409
        return jsonify({"error": "We don't recognise that key. Check for typos."}), 404

    token = keysgen.make_download_token()
    expires = time.time() + config.DOWNLOAD_TOKEN_TTL_HOURS * 3600
    db.set_download_token(row["id"], token, expires)

    url = f"{config.SITE_URL}/dl/{token}"
    return jsonify({"ok": True, "tier": row["tier"], "download_url": url, "redirect": url})


@app.get("/dl/<token>")
def download(token: str):
    row = db.get_key_by_token(token)
    if not row:
        return jsonify({"error": "Invalid or expired download link."}), 404
    if row["token_expires_at"] and row["token_expires_at"] < time.time():
        return jsonify({"error": "This download link expired. Redeem your key again."}), 410
    if row["downloads_used"] >= config.DOWNLOAD_MAX_ATTEMPTS:
        return jsonify({"error": "Download limit reached for this link."}), 429

    product = config.PRODUCTS.get(row["tier"])
    if not product:
        return jsonify({"error": "Unknown product tier."}), 500
    fpath = os.path.join(config.PRODUCTS_DIR, product["zip"])
    if not os.path.isfile(fpath):
        app.logger.error("Product file missing: %s", fpath)
        return jsonify({"error": "File temporarily unavailable."}), 500

    db.bump_download(row["id"])
    return send_file(fpath, as_attachment=True, download_name=product["zip"])


# --- ops ---------------------------------------------------------------------
@app.get("/api/health")
def health():
    return jsonify({"ok": True, "env": config.PAYPAL_ENV, **db.stats()})


def create_app() -> Flask:
    db.init_db()
    problems = config.validate()
    for p in problems:
        app.logger.warning("config: %s", p)
    return app


if __name__ == "__main__":
    create_app()
    app.run(host="127.0.0.1", port=int(config.env("PORT", "8000")), debug=False)
