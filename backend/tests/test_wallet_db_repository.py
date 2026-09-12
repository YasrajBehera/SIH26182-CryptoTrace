"""Regression tests for the canonical ``(chain, tx_hash)`` dedup contract in
wallet persistence.

A single real transaction can be reported multiple times (Alchemy returns the
same tx_hash in both directions for a wallet) so the persistence layer must
collapse the batch by ``(chain, tx_hash)`` instead of letting two pending rows
collide on the ``uq_transactions_chain_tx_hash`` unique constraint. The same
tx_hash on a *different* chain is a different transaction and must be kept.

The in-memory store cases always run. The PostgreSQL cases run whenever a real
Postgres is reachable and are skipped otherwise so the hermetic CI suite stays
network-free.
"""

from datetime import datetime, timezone

import pytest

from app.db import SessionLocal
from wallets.repository import DbWalletRepository, MemoryWalletRepository

ADDR = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
COUNTERPARTY = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
H1 = "0x" + "1" * 64
H2 = "0x" + "2" * 64


def _tx(
    tx_hash,
    chain="eth",
    value="5",
    from_address=COUNTERPARTY,
    to_address=ADDR,
    block_number=100,
    block_timestamp=1704067200,
):
    return {
        "chain": chain,
        "tx_hash": tx_hash,
        "block_number": block_number,
        "block_timestamp": block_timestamp,
        "from_address": from_address,
        "to_address": to_address,
        "value": value,
        "token_symbol": "ETH",
    }


class TestMemoryWalletDedup:
    """The (chain, tx_hash) canonical identity in the always-running store."""

    def test_duplicate_tx_hash_in_same_batch(self):
        repo = MemoryWalletRepository()
        result = repo.store_transactions(
            [
                _tx(H1, from_address=COUNTERPARTY, to_address=ADDR),
                _tx(H1, from_address=ADDR, to_address=COUNTERPARTY),
            ]
        )
        assert result["inserted"] == 1
        assert repo.transaction_count() == 1
        rows = repo.list_transactions(address=ADDR, chain="eth")
        assert len(rows) == 1
        assert rows[0]["tx_hash"] == H1

    def test_same_tx_hash_across_different_chains(self):
        repo = MemoryWalletRepository()
        result = repo.store_transactions(
            [
                _tx(H1, chain="eth"),
                _tx(H1, chain="polygon"),
            ]
        )
        assert result["inserted"] == 2
        assert repo.transaction_count() == 2
        assert len(repo.list_transactions(address=ADDR, chain="eth")) == 1
        assert len(repo.list_transactions(address=ADDR, chain="polygon")) == 1

    def test_existing_transaction_reingested(self):
        repo = MemoryWalletRepository()
        repo.store_transactions([_tx(H1, value="5")])
        result = repo.store_transactions([_tx(H1, value="9")])
        assert result["inserted"] == 0
        assert result["updated"] == 1
        assert repo.transaction_count() == 1


@pytest.fixture
def db_repo(monkeypatch):
    """A live-Postgres wallet repository, skipped when Postgres is down."""
    import app.db

    monkeypatch.setattr(app.db, "_database_available", True)
    try:
        app.db.ensure_database_tables()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"PostgreSQL unreachable, skipping live persistence tests: {exc}")
    return DbWalletRepository()


_PERSISTED_KEYS = []


def _persist(repo, *rows):
    result = repo.store_transactions(list(rows))
    for row in rows:
        _PERSISTED_KEYS.append(((row.get("chain") or "eth"), (row.get("tx_hash") or "").lower()))
    return result


@pytest.fixture(autouse=True)
def _cleanup_persisted(monkeypatch):
    import app.db

    monkeypatch.setattr(app.db, "_database_available", True)
    yield
    try:
        from app import models

        with SessionLocal() as session:
            for chain, tx_hash in set(_PERSISTED_KEYS):
                session.query(models.Transaction).filter(
                    models.Transaction.chain == chain,
                    models.Transaction.tx_hash == tx_hash,
                ).delete()
            session.commit()
    except Exception:
        pass
    _PERSISTED_KEYS.clear()


class TestDbWalletDedup:
    """Duplicates must not violate uq_transactions_chain_tx_hash in Postgres."""

    def test_duplicate_tx_hash_in_same_batch(self, db_repo):
        result = _persist(
            db_repo,
            _tx(H1, from_address=COUNTERPARTY, to_address=ADDR),
            _tx(H1, from_address=ADDR, to_address=COUNTERPARTY),
        )
        assert result["inserted"] == 1
        rows = db_repo.list_transactions(address=ADDR, chain="eth")
        assert len(rows) == 1
        assert rows[0]["tx_hash"] == H1

    def test_same_tx_hash_across_different_chains(self, db_repo):
        result = _persist(
            db_repo,
            _tx(H1, chain="eth"),
            _tx(H1, chain="polygon"),
        )
        assert result["inserted"] == 2
        assert len(db_repo.list_transactions(address=ADDR, chain="eth")) == 1
        assert len(db_repo.list_transactions(address=ADDR, chain="polygon")) == 1

    def test_reingest_does_not_duplicate_or_raise(self, db_repo):
        first = _persist(db_repo, _tx(H1, value="5"))
        assert first["inserted"] == 1
        second = _persist(db_repo, _tx(H1, value="9"))
        assert second["inserted"] == 0
        assert second["updated"] == 1
        rows = db_repo.list_transactions(address=ADDR, chain="eth")
        assert len(rows) == 1
        assert rows[0]["tx_hash"] == H1

    def test_batch_partially_existing_partially_new(self, db_repo):
        _persist(db_repo, _tx(H1, value="5"))
        result = _persist(
            db_repo,
            _tx(H1, value="9"),
            _tx(H2, value="7"),
        )
        assert result["inserted"] == 1
        assert result["updated"] == 1
        rows = db_repo.list_transactions(address=ADDR, chain="eth")
        assert {r["tx_hash"] for r in rows} == {H1, H2}
        assert db_repo.list_transactions(address=ADDR, chain="eth")[0]["block_timestamp"] == datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()