import argparse
from datetime import datetime, timezone
from decimal import Decimal

from app.db import SessionLocal, ensure_database_tables
from app.models import Transaction
from graph.synthetic import generate_transactions


def seed(count: int = 50) -> int:
    ensure_database_tables()
    transactions = generate_transactions(count=count)
    with SessionLocal() as db:
        for index, synthetic in enumerate(transactions):
            db.add(
                Transaction(
                    tx_hash=synthetic.tx_hash,
                    chain=synthetic.chain,
                    block_number=index + 1,
                    block_timestamp=datetime.fromtimestamp(
                        synthetic.block_timestamp, tz=timezone.utc
                    ),
                    from_address=synthetic.from_address,
                    to_address=synthetic.to_address,
                    value=Decimal(synthetic.value),
                )
            )
        db.commit()
    return len(transactions)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed synthetic transactions into PostgreSQL")
    parser.add_argument("--count", type=int, default=50, help="number of synthetic transactions")
    args = parser.parse_args()
    inserted = seed(count=args.count)
    print(f"seeded {inserted} synthetic transactions")


if __name__ == "__main__":
    main()