"""Secure demo-user seeding CLI.

Usage:
    python -m app.auth.seed            # seed via DEMO_SEED_PASSWORD or generate
    python -m app.auth.seed --reset    # re-hash existing demo users with a new password

SECURITY: No plaintext password is ever written to disk, logs, or git. The seed
reads ``DEMO_SEED_PASSWORD`` from env; otherwise a random one-time password is
generated and printed ONCE to stdout underneath a loud DEMO-ONLY warning.
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed CryptoTrace demo users securely.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset demo user passwords (re-hashes existing accounts).",
    )
    args = parser.parse_args(argv)

    from app.auth.service import UserService, get_user_service
    from app.db import database_available, ensure_database_tables

    db_ok = database_available()
    if db_ok:
        try:
            ensure_database_tables()
        except Exception as exc:  # never block seeding on schema issues offline
            print(f"[cryptotrace] Schema ensure skipped: {exc}", file=sys.stderr)

    service: UserService = get_user_service()
    result = service.ensure_demo_seed(password=None, reset=args.reset)

    if not result["seeded"]:
        print(f"[cryptotrace] Demo seed skipped: {result['reason']}.")
        return 0

    print("[cryptotrace] Demo users provisioned (PBKDF2-hashed passwords):")
    for spec in ["admin", "senior_investigator", "investigator", "analyst", "reviewer"]:
        print(f"  - {spec}")

    if result.get("generated") and result.get("password"):
        print()
        print("=" * 70)
        print("DEMO ONLY — THE GENERATED DEMO PASSWORD IS SHOWN ONCE AND NOT STORED.")
        print("Rotate it before any non-demo use. Never commit or share it.")
        print("=" * 70)
        print(f"DEMO PW: {result['password']}")
        print("=" * 70)
    else:
        print()
        print("[cryptotrace] Demo password was read from DEMO_SEED_PASSWORD env; it is not printed.")
        print("Use these accounts only for demonstration of the security UI.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())