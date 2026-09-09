from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import SQLAlchemyError

from graph.db_loader import GraphLoadError, load_transactions


class FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def order_by(self, *args):
        return self

    def yield_per(self, batch):
        return iter(self._rows)


class FakeDbSession:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def query(self, model):
        return FakeQuery(self.rows)


class FailingSession:
    def __enter__(self):
        raise SQLAlchemyError("connection refused")

    def __exit__(self, *args):
        return False


class FailingQueryIter:
    def order_by(self, *args):
        return self

    def yield_per(self, batch):
        raise SQLAlchemyError("query failed")


class FailingQuerySession:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def query(self, model):
        return FailingQueryIter()


def to_row():
    return SimpleNamespace(
        chain="eth",
        tx_hash="0x" + "a" * 64,
        block_timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        from_address="0x" + "1" * 40,
        to_address="0x" + "2" * 40,
        value=Decimal("1000000000000000000"),
    )


def test_load_transactions_empty_database():
    rows = list(load_transactions(lambda: FakeDbSession([])))
    assert rows == []


def test_load_transactions_projects_required_fields():
    rows = list(load_transactions(lambda: FakeDbSession([to_row()])))
    assert len(rows) == 1
    assert set(rows[0]) == {
        "chain",
        "tx_hash",
        "block_timestamp",
        "from_address",
        "to_address",
        "value",
    }
    assert rows[0]["chain"] == "eth"
    assert rows[0]["value"] == Decimal("1000000000000000000")


def test_load_transactions_raises_on_session_error():
    with pytest.raises(GraphLoadError):
        list(load_transactions(lambda: FailingSession()))


def test_load_transactions_raises_on_query_error():
    with pytest.raises(GraphLoadError):
        list(load_transactions(lambda: FailingQuerySession()))