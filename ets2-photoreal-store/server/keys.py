"""
License-key generation and verification.

Design notes
------------
* 20 characters drawn from a 32-symbol alphabet  ->  32^20 = 2^100 combos.
  Brute-forcing a valid key is not feasible.
* Ambiguous glyphs (0/O, 1/I/L) are excluded so buyers can retype by hand.
* Keys are displayed grouped (XXXXX-XXXXX-XXXXX-XXXXX) but the dashes are
  cosmetic; anything non-alphanumeric is stripped before checking.
* Only the SHA-256 of the normalised key is ever stored. The raw key exists
  exactly once, in the buyer's email. A database leak does not leak keys.
"""
import hashlib
import secrets

# 32 symbols, no 0/O/1/I/L. 32^20 = 2^100 entropy.
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
KEY_LEN = 20
GROUP = 5  # XXXXX-XXXXX-XXXXX-XXXXX


def generate_key() -> str:
    raw = "".join(secrets.choice(ALPHABET) for _ in range(KEY_LEN))
    return format_key(raw)


def format_key(raw: str) -> str:
    return "-".join(raw[i : i + GROUP] for i in range(0, KEY_LEN, GROUP))


def normalise(key: str) -> str:
    """Uppercase and keep only alphanumeric characters."""
    return "".join(c for c in key.upper() if c.isalnum())


def is_valid_format(key: str) -> bool:
    n = normalise(key)
    if len(n) != KEY_LEN:
        return False
    return all(c in ALPHABET for c in n)


def key_hash(key: str) -> str:
    """Stable hash of the normalised key. This is all we store."""
    return hashlib.sha256(normalise(key).encode("utf-8")).hexdigest()


def make_download_token() -> str:
    return secrets.token_hex(24)  # 48 hex chars
