"""
Central configuration for the ETS2 Photoreal storefront.

All secrets come from environment variables, loaded from a `.env` file at the
project root (see `.env.example`). NOTHING sensitive is ever hardcoded here.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))


def _load_dotenv(path: str) -> None:
    """Minimal .env loader (avoids an extra dependency)."""
    if not os.path.isfile(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip()
                if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                    val = val[1:-1]
                # do not clobber vars already set in the real environment
                os.environ.setdefault(key, val)
    except OSError:
        pass


_load_dotenv(os.path.join(ROOT, ".env"))


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def env_bool(key: str, default: bool = False) -> bool:
    v = os.environ.get(key)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


# --- site -------------------------------------------------------------------
SITE_NAME = env("SITE_NAME", "ETS2 Photorealism")
SITE_URL = env("SITE_URL", "http://localhost:8000").rstrip("/")

# --- storage ----------------------------------------------------------------
DATA_DIR = env("DATA_DIR", os.path.join(ROOT, "data"))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = env("DB_PATH", os.path.join(DATA_DIR, "store.db"))

PRODUCTS_DIR = env("PRODUCTS_DIR", os.path.join(ROOT, "products"))

# --- pricing (CAD) ----------------------------------------------------------
# Prices are charged in CAD. Totals are computed SERVER-SIDE from the before-tax
# price and the tax rate, so the browser can never tamper with the amount.
# If you want a fixed total instead of a computed one, set TOTAL_CAD_* in .env.
CURRENCY = "CAD"
PRICE_CAD_STANDARD = float(env("PRICE_CAD_STANDARD", "6.99"))
PRICE_CAD_PREMIUM = float(env("PRICE_CAD_PREMIUM", "12.99"))
TAX_RATE = float(env("TAX_RATE", "0.14"))  # 14%
TOTAL_CAD_STANDARD = env("TOTAL_CAD_STANDARD", "")  # optional override
TOTAL_CAD_PREMIUM = env("TOTAL_CAD_PREMIUM", "")    # optional override


def _total(override: str, price: float) -> float:
    if override.strip():
        return round(float(override), 2)
    return round(price * (1.0 + TAX_RATE), 2)


# Product catalog. `tier` must match the tier stored against a license key and
# determines which zip is served on redemption.
PRODUCTS = {
    "standard": {
        "key": "standard",
        "name": "ETS2 Photorealism - Standard",
        "tier": "standard",
        "blurb": "Tiers 1 & 2. Full photoreal post-processing stack. No depth buffer needed.",
        "price": PRICE_CAD_STANDARD,
        "total": _total(TOTAL_CAD_STANDARD, PRICE_CAD_STANDARD),
        "zip": "ETS2_Photoreal_Standard.zip",
        "badge": "STANDARD",
    },
    "premium": {
        "key": "premium",
        "name": "ETS2 Photorealism - Premium",
        "tier": "premium",
        "blurb": "Tiers 3 & 4. Adds ambient occlusion, depth haze, lens bloom + DOF. The reference look.",
        "price": PRICE_CAD_PREMIUM,
        "total": _total(TOTAL_CAD_PREMIUM, PRICE_CAD_PREMIUM),
        "zip": "ETS2_Photoreal_Premium.zip",
        "badge": "PREMIUM",
    },
}

# --- PayPal -----------------------------------------------------------------
PAYPAL_ENV = env("PAYPAL_ENV", "sandbox").strip().lower()  # "sandbox" or "live"
PAYPAL_CLIENT_ID = env("PAYPAL_CLIENT_ID", "")
PAYPAL_SECRET = env("PAYPAL_SECRET", "")
PAYPAL_API_BASE = (
    "https://api-m.paypal.com" if PAYPAL_ENV == "live" else "https://api-m.sandbox.paypal.com"
)

# --- email (SMTP) -----------------------------------------------------------
SMTP_HOST = env("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(env("SMTP_PORT", "587"))
SMTP_USER = env("SMTP_USER", "")
SMTP_PASS = env("SMTP_PASS", "")          # for Gmail: use an App Password
SMTP_STARTTLS = env_bool("SMTP_STARTTLS", True)
MAIL_FROM = env("MAIL_FROM", SMTP_USER or "noreply@example.com")
MAIL_FROM_NAME = env("MAIL_FROM_NAME", "ETS2 Photorealism")
# Where purchase notifications (and PayPal-email fallback) are sent.
ADMIN_EMAIL = env("ADMIN_EMAIL", SMTP_USER or "")

# --- delivery / security knobs ---------------------------------------------
# A redeemed key issues a short-lived download token so a dropped connection
# doesn't lock the buyer out. The FILES are theirs forever; the KEY is one-time.
DOWNLOAD_TOKEN_TTL_HOURS = int(env("DOWNLOAD_TOKEN_TTL_HOURS", "24"))
DOWNLOAD_MAX_ATTEMPTS = int(env("DOWNLOAD_MAX_ATTEMPTS", "5"))
REDEEM_RATE_LIMIT = int(env("REDEEM_RATE_LIMIT", "10"))     # per IP per hour
ORDER_RATE_LIMIT = int(env("ORDER_RATE_LIMIT", "15"))       # per IP per hour

SECRET_KEY = env("SECRET_KEY", "")


def validate() -> list:
    """Return a list of human-readable problems that would break checkout."""
    problems = []
    if not PAYPAL_CLIENT_ID or not PAYPAL_SECRET:
        problems.append(
            "PAYPAL_CLIENT_ID / PAYPAL_SECRET are not set (get them from "
            "developer.paypal.com). Checkout will not work."
        )
    if not SMTP_USER or not SMTP_PASS:
        problems.append(
            "SMTP_USER / SMTP_PASS are not set. Purchase emails will not send "
            "(Gmail: create an App Password)."
        )
    if not ADMIN_EMAIL:
        problems.append("ADMIN_EMAIL is not set; nowhere to send order notices.")
    if not SECRET_KEY:
        problems.append("SECRET_KEY is not set; set a long random string.")
    return problems
