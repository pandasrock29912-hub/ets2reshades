"""
Admin command-line tools.

Run from the project root, e.g.:
    python3 -m server.cli stats
    python3 -m server.cli orders
    python3 -m server.cli reissue <order_id> [email@example.com]

`reissue` is the safe recovery path for "buyer lost the email". Because keys are
stored only as hashes we cannot recover the original, so this mints a NEW key for
that paid order and emails it (the old key, if any, still works too).
"""
import sys

from . import config, db, mailer


def _rowdict(r):
    return dict(r) if r is not None else None


def cmd_stats() -> None:
    s = db.stats()
    print(f"Paid orders : {s['orders_paid']}")
    print(f"Keys issued : {s['keys_issued']}")
    print(f"Keys redeemed: {s['keys_redeemed']}")


def cmd_orders() -> None:
    con = db._connect()
    try:
        rows = con.execute(
            "SELECT id,tier,email,payer_email,amount,status,datetime(created_at,'unixepoch') "
            "AS created FROM orders ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
    finally:
        con.close()
    if not rows:
        print("No orders yet.")
        return
    for r in rows:
        print(
            f"{r['created']}  {r['status']:7s} {r['tier']:9s} "
            f"{r['amount']:>6s} {config.CURRENCY}  {r['email']}"
        )


def cmd_reissue(order_id: str, email: str = None) -> None:
    order = db.get_order(order_id)
    if not order:
        print(f"No order with id {order_id}")
        sys.exit(1)
    if order["status"] != "paid":
        print(f"Order {order_id} is '{order['status']}', not paid. Refusing to issue.")
        sys.exit(1)
    key = db.issue_key(order["tier"], order["id"])
    to = email or order["email"] or order["payer_email"]
    if not to:
        print("No email on this order. Pass one: reissue <order_id> you@example.com")
        sys.exit(1)
    mailer.send_key(to, key, order["tier"])
    print(f"New {order['tier']} key issued and emailed to {to}")
    print(f"  (old key, if any, remains valid — both unlock one download each)")


def main(argv) -> None:
    db.init_db()
    if not argv:
        print(__doc__)
        return
    cmd, *rest = argv
    if cmd == "stats":
        cmd_stats()
    elif cmd == "orders":
        cmd_orders()
    elif cmd == "reissue":
        if not rest:
            print("usage: reissue <order_id> [email]")
            sys.exit(1)
        cmd_reissue(rest[0], rest[1] if len(rest) > 1 else None)
    else:
        print(f"Unknown command: {cmd}\n")
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1:])
