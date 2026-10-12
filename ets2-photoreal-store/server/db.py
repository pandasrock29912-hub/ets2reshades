"""
SQLite persistence: orders and license keys.

A fresh connection is opened per operation (cheap for this scale, and avoids
cross-thread handle sharing under Flask). WAL mode keeps concurrent reads happy.
"""
import os
import sqlite3
import time
import uuid

from . import config, keys as keysgen

_SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id                TEXT PRIMARY KEY,          -- our internal UUID
    paypal_order_id   TEXT UNIQUE,               -- PayPal's order id
    tier              TEXT NOT NULL,             -- 'standard' | 'premium'
    email             TEXT NOT NULL,             -- buyer-entered email
    payer_email       TEXT,                      -- email returned by PayPal
    amount            TEXT NOT NULL,             -- charged total, e.g. '7.97'
    currency          TEXT NOT NULL DEFAULT 'CAD',
    status            TEXT NOT NULL DEFAULT 'created',  -- created|paid|failed|refunded
    created_at        REAL NOT NULL,
    updated_at        REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS keys (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    key_hash           TEXT NOT NULL UNIQUE,     -- sha256(normalised key)
    key_pretty         TEXT NOT NULL,            -- grouped form, for admin lookup
    tier               TEXT NOT NULL,
    order_id           TEXT,                     -- orders.id
    created_at         REAL NOT NULL,
    used_at            REAL,                     -- when the key was first redeemed
    download_token     TEXT,                     -- short-lived access token
    token_expires_at   REAL,
    downloads_used     INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_keys_token ON keys(download_token);
CREATE INDEX IF NOT EXISTS idx_orders_paypal ON orders(paypal_order_id);
"""


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(config.DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    return con


def init_db() -> None:
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    with _connect() as con:
        con.executescript(_SCHEMA)


def now() -> float:
    return time.time()


# --- orders -----------------------------------------------------------------
def create_order(tier: str, email: str, amount: str) -> str:
    oid = uuid.uuid4().hex
    t = now()
    with _connect() as con:
        con.execute(
            "INSERT INTO orders (id,tier,email,amount,currency,status,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (oid, tier, email, amount, config.CURRENCY, "created", t, t),
        )
    return oid


def attach_paypal_order(order_id: str, paypal_order_id: str) -> None:
    with _connect() as con:
        con.execute(
            "UPDATE orders SET paypal_order_id=?, updated_at=? WHERE id=?",
            (paypal_order_id, now(), order_id),
        )


def get_order(order_id: str):
    with _connect() as con:
        return con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()


def get_order_by_paypal(paypal_order_id: str):
    with _connect() as con:
        return con.execute(
            "SELECT * FROM orders WHERE paypal_order_id=?", (paypal_order_id,)
        ).fetchone()


def set_order_status(order_id: str, status: str, payer_email: str = None) -> None:
    with _connect() as con:
        if payer_email is not None:
            con.execute(
                "UPDATE orders SET status=?, payer_email=?, updated_at=? WHERE id=?",
                (status, payer_email, now(), order_id),
            )
        else:
            con.execute(
                "UPDATE orders SET status=?, updated_at=? WHERE id=?",
                (status, now(), order_id),
            )


# --- keys -------------------------------------------------------------------
def issue_key(tier: str, order_id: str) -> str:
    """Generate a key, store only its hash, and return the raw key ONCE."""
    raw = keysgen.generate_key()
    with _connect() as con:
        con.execute(
            "INSERT INTO keys (key_hash,key_pretty,tier,order_id,created_at)"
            " VALUES (?,?,?,?,?)",
            (keysgen.key_hash(raw), raw, tier, order_id, now()),
        )
    return raw


def claim_key(raw_key: str):
    """
    Atomically redeem a key: returns the key row on first successful use,
    or None if the key is unknown / malformed / already used.

    The `... WHERE used_at IS NULL` guard makes redemption one-time even if two
    requests race: exactly one UPDATE can match.
    """
    h = keysgen.key_hash(raw_key)
    with _connect() as con:
        cur = con.execute(
            "UPDATE keys SET used_at=? WHERE key_hash=? AND used_at IS NULL",
            (now(), h),
        )
        if cur.rowcount != 1:
            return None
        return con.execute("SELECT * FROM keys WHERE key_hash=?", (h,)).fetchone()


def key_already_used(raw_key: str) -> bool:
    """Distinguish 'already used' from 'never existed' for a nicer error."""
    h = keysgen.key_hash(raw_key)
    with _connect() as con:
        row = con.execute("SELECT used_at FROM keys WHERE key_hash=?", (h,)).fetchone()
    return bool(row and row["used_at"])


def set_download_token(key_id: int, token: str, expires_at: float) -> None:
    with _connect() as con:
        con.execute(
            "UPDATE keys SET download_token=?, token_expires_at=?, downloads_used=0"
            " WHERE id=?",
            (token, expires_at, key_id),
        )


def get_key_by_token(token: str):
    with _connect() as con:
        return con.execute(
            "SELECT * FROM keys WHERE download_token=?", (token,)
        ).fetchone()


def bump_download(key_id: int) -> None:
    with _connect() as con:
        con.execute(
            "UPDATE keys SET downloads_used=downloads_used+1 WHERE id=?", (key_id,)
        )


# --- admin helpers ----------------------------------------------------------
def stats() -> dict:
    with _connect() as con:
        paid = con.execute("SELECT COUNT(*) c FROM orders WHERE status='paid'").fetchone()
        redeemed = con.execute(
            "SELECT COUNT(*) c FROM keys WHERE used_at IS NOT NULL"
        ).fetchone()
        issued = con.execute("SELECT COUNT(*) c FROM keys").fetchone()
    return {
        "orders_paid": paid["c"],
        "keys_issued": issued["c"],
        "keys_redeemed": redeemed["c"],
    }
