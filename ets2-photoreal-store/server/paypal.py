"""
Minimal PayPal REST v2 client (create / capture / inspect orders).

Why server-side: the browser is never trusted. The AMOUNT and CURRENCY are set
by us here, and a payment only counts once PayPal reports the order as
COMPLETED from a server-to-server call. A client-side "return URL" alone is
never treated as proof of payment.
"""
import base64
import threading
import time

import requests

from . import config

_token_lock = threading.Lock()
_token_cache = {"token": None, "expires_at": 0.0}


def _auth_header() -> str:
    cred = f"{config.PAYPAL_CLIENT_ID}:{config.PAYPAL_SECRET}".encode()
    return "Basic " + base64.b64encode(cred).decode()


def get_access_token(force: bool = False) -> str:
    with _token_lock:
        if not force and _token_cache["token"] and time.time() < _token_cache["expires_at"] - 30:
            return _token_cache["token"]
        resp = requests.post(
            f"{config.PAYPAL_API_BASE}/v1/oauth2/token",
            headers={
                "Authorization": _auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        _token_cache["token"] = data["access_token"]
        _token_cache["expires_at"] = time.time() + float(data.get("expires_in", 32400))
        return _token_cache["token"]


def _api(method: str, path: str, json_body=None) -> requests.Response:
    """Call the PayPal API once, refreshing the token once on a 401."""
    def do() -> requests.Response:
        return requests.request(
            method,
            f"{config.PAYPAL_API_BASE}{path}",
            headers={
                "Authorization": f"Bearer {get_access_token()}",
                "Content-Type": "application/json",
            },
            json=json_body,
            timeout=45,
        )

    resp = do()
    if resp.status_code == 401:  # token expired mid-flight
        get_access_token(force=True)
        resp = do()
    return resp


class PayPalError(RuntimeError):
    pass


def create_order(amount: str, tier: str, our_order_id: str, return_url: str, cancel_url: str) -> str:
    """
    Create a CAPTURE-intent order with the amount fixed server-side.
    `custom_id` carries our internal order id so capture can be reconciled.
    """
    body = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": our_order_id[:16],
                "custom_id": our_order_id,
                "invoice_id": f"ETS2-{our_order_id[:12].upper()}",
                "description": f"ETS2 Photorealism - {tier}",
                "amount": {"currency_code": config.CURRENCY, "value": amount},
            }
        ],
        "application_context": {
            "brand_name": config.SITE_NAME,
            "landing_page": "BILLING",
            "user_action": "PAY_NOW",
            "return_url": return_url,
            "cancel_url": cancel_url,
        },
    }
    resp = _api("POST", "/v2/checkout/orders", body)
    if resp.status_code not in (200, 201):
        raise PayPalError(f"create_order failed ({resp.status_code}): {resp.text[:400]}")
    return resp.json()["id"]


def capture_order(paypal_order_id: str) -> dict:
    """Capture an approved order. Raises PayPalError if PayPal refuses."""
    resp = _api("POST", f"/v2/checkout/orders/{paypal_order_id}/capture", {})
    if resp.status_code not in (200, 201):
        raise PayPalError(f"capture failed ({resp.status_code}): {resp.text[:400]}")
    return resp.json()


def get_order(paypal_order_id: str) -> dict:
    resp = _api("GET", f"/v2/checkout/orders/{paypal_order_id}", None)
    if resp.status_code != 200:
        raise PayPalError(f"get_order failed ({resp.status_code}): {resp.text[:400]}")
    return resp.json()


def is_completed(capture_json: dict) -> bool:
    """True only if PayPal says the money actually cleared."""
    if capture_json.get("status") == "COMPLETED":
        return True
    # Fall back to inspecting per-unit capture status.
    for unit in capture_json.get("purchase_units", []):
        for cap in unit.get("payments", {}).get("captures", []):
            if cap.get("status") == "COMPLETED":
                return True
    return False


def payer_email(order_json: dict) -> str:
    try:
        return order_json.get("payer", {}).get("email_address") or ""
    except AttributeError:
        return ""
