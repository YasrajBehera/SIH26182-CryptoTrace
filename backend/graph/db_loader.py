from typing import Callable, Dict, Iterator

from sqlalchemy.exc import SQLAlchemyError

from app.db import SessionLocal
from app.models import Transaction

default_session_factory = SessionLocal

TRANSACTION_FIELDS = [
    "chain",
    "tx_hash",
    "block_timestamp",
    "from_address",
    "to_address",
    "value",
]


class GraphLoadError(RuntimeError):
    """Raised when transaction data cannot be read from the database."""


def load_transactions(
    db_session_factory: Callable = default_session_factory,
    batch_size: int = 1000,
) -> Iterator[Dict]:
    try:
        with db_session_factory() as db:
            rows = (
                db.query(Transaction).order_by(Transaction.id).yield_per(batch_size)
            )
            for tx in rows:
                yield {field: getattr(tx, field, None) for field in TRANSACTION_FIELDS}
    except SQLAlchemyError as exc:
        raise GraphLoadError(
            f"Failed to load transactions from the database: {exc}"
        ) from exc