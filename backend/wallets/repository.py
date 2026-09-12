"""Wallet repositories: durable SQLAlchemy backend when Postgres is reachable
and a deterministic in-memory store otherwise (offline tests/demos).

Transfer row shape (Agreed normal form used across the codebase):
    {chain, tx_hash, block_number, block_timestamp (int unix), from_address,
     to_address, value (str), fee (str|None), token_symbol (str|None)}
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import func

from app import models
from app.db import SessionLocal, database_available


def _safe_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_decimal(value) -> Decimal:
    try:
        return Decimal(str(value))
    except (TypeError, ValueError, ArithmeticError):
        return Decimal(0)


class WalletRepository:
    is_demo: bool = True

    def store_transactions(self, rows: List[Dict]) -> Dict:
        """Upsert transfer rows, returning {inserted, updated, skipped}."""
        raise NotImplementedError

    def transaction_count(self) -> int:
        raise NotImplementedError

    def list_transactions(
        self,
        address: Optional[str] = None,
        chain: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        raise NotImplementedError

    def coin_volumes(self, address: str, chain: str) -> Dict:
        """Return {count, first_seen, last_activity, incoming, outgoing}."""
        raise NotImplementedError

    def upsert_summary(self, summary: Dict) -> Dict:
        """Persist a computed wallet summary and return the stored dict."""
        raise NotImplementedError

    def get_summary(self, address: str, chain: str) -> Optional[Dict]:
        raise NotImplementedError


class MemoryWalletRepository(WalletRepository):
    is_demo = True

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._transactions: Dict[tuple, Dict] = {}
        self._summaries: Dict[tuple, Dict] = {}

    def store_transactions(self, rows: List[Dict]) -> Dict:
        inserted = 0
        updated = 0
        skipped = 0
        with self._lock:
            for row in rows:
                tx_hash = (row.get("tx_hash") or "").lower()
                chain = row.get("chain") or "eth"
                if not tx_hash or not row.get("from_address") or not row.get("to_address"):
                    skipped += 1
                    continue
                key = (chain, tx_hash)
                existing = key in self._transactions
                self._transactions[key] = dict(row)
                if existing:
                    updated += 1
                else:
                    inserted += 1
        return {"inserted": inserted, "updated": updated, "skipped": skipped}

    def transaction_count(self) -> int:
        with self._lock:
            return len(self._transactions)

    def list_transactions(
        self,
        address: Optional[str] = None,
        chain: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        with self._lock:
            rows = list(self._transactions.values())
        if chain:
            rows = [r for r in rows if r.get("chain") == chain]
        if address:
            needle = address.lower()
            rows = [
                r
                for r in rows
                if (r.get("from_address") or "").lower() == needle
                or (r.get("to_address") or "").lower() == needle
            ]
        rows.sort(key=lambda r: _safe_int(r.get("block_timestamp")))
        if limit is not None:
            rows = rows[:limit]
        return rows

    def coin_volumes(self, address: str, chain: str) -> Dict:
        rows = self.list_transactions(address=address, chain=chain)
        needle = address.lower()
        incoming = _safe_decimal(0)
        outgoing = _safe_decimal(0)
        first_ts = None
        last_ts = None
        for row in rows:
            ts = _safe_int(row.get("block_timestamp"))
            if first_ts is None or ts < first_ts:
                first_ts = ts
            if last_ts is None or ts > last_ts:
                last_ts = ts
            value = _safe_decimal(row.get("value"))
            if (row.get("to_address") or "").lower() == needle:
                incoming += value
            elif (row.get("from_address") or "").lower() == needle:
                outgoing += value
        return {
            "count": len(rows),
            "first_seen": first_ts,
            "last_activity": last_ts,
            "incoming": incoming,
            "outgoing": outgoing,
        }

    def upsert_summary(self, summary: Dict) -> Dict:
        address = (summary.get("address") or "").lower()
        chain = summary.get("chain") or "eth"
        key = (address, chain)
        with self._lock:
            prior = dict(self._summaries.get(key, {}))
            merged = {
                "address": summary.get("address"),
                "chain": chain,
                "first_seen": summary.get("first_seen") or prior.get("first_seen"),
                "last_activity": summary.get("last_activity") or prior.get("last_activity"),
                "transaction_count": summary.get("transaction_count", prior.get("transaction_count", 0)),
                "incoming_volume": str(summary.get("incoming_volume", prior.get("incoming_volume", "0"))),
                "outgoing_volume": str(summary.get("outgoing_volume", prior.get("outgoing_volume", "0"))),
                "balance": summary.get("balance"),
                "risk": summary.get("risk", prior.get("risk", "unknown")),
                "risk_score": summary.get("risk_score") if summary.get("risk_score") is not None else prior.get("risk_score"),
                "investigation_status": summary.get(
                    "investigation_status",
                    prior.get("investigation_status", "analyzed"),
                ),
            }
            self._summaries[key] = merged
        return merged

    def get_summary(self, address: str, chain: str) -> Optional[Dict]:
        with self._lock:
            record = self._summaries.get((address.lower(), chain))
            return dict(record) if record else None


class DbWalletRepository(WalletRepository):
    is_demo = False

    @staticmethod
    def _existing_keys(session, keys) -> set:
        """Return the subset of ``(chain, tx_hash)`` keys already in the table.

        Querying in one OR-filtered pass (chunked for very large batches) keeps
        the check atomic within the caller's transaction and avoids a row-by-row
        ``first()`` probe for every transfer.
        """
        from sqlalchemy import or_

        existing = set()
        for start in range(0, len(keys), 500):
            chunk = keys[start : start + 500]
            condition = or_(
                *[
                    (models.Transaction.chain == chain)
                    & (models.Transaction.tx_hash == tx_hash)
                    for chain, tx_hash in chunk
                ]
            )
            for row in session.query(models.Transaction).filter(condition).all():
                existing.add((row.chain, row.tx_hash))
        return existing

    def store_transactions(self, rows: List[Dict]) -> Dict:
        inserted = 0
        updated = 0
        skipped = 0
        # Canonical identity is (chain, tx_hash). Alchemy can report the same
        # transaction to and from a wallet, so within one incoming batch a tx_hash
        # may legitimately appear more than once. Collapse the batch first so we
        # never hand the unique constraint two pending rows with the same key.
        pending: Dict[tuple, Dict] = {}
        for row in rows:
            tx_hash = (row.get("tx_hash") or "").lower()
            chain = row.get("chain") or "eth"
            if not tx_hash or not row.get("from_address") or not row.get("to_address"):
                skipped += 1
                continue
            key = (chain, tx_hash)
            if key in pending:
                updated += 1
                continue
            pending[key] = row

        with SessionLocal() as session:
            existing_keys = self._existing_keys(session, list(pending.keys()))
            for key, row in pending.items():
                if key in existing_keys:
                    updated += 1
                    continue
                chain, tx_hash = key
                session.add(
                    models.Transaction(
                        tx_hash=tx_hash,
                        chain=chain,
                        block_number=_safe_int(row.get("block_number")),
                        block_timestamp=datetime.fromtimestamp(
                            _safe_int(row.get("block_timestamp")), tz=timezone.utc
                        ),
                        from_address=row.get("from_address", ""),
                        to_address=row.get("to_address", ""),
                        value=_safe_decimal(row.get("value")),
                        fee=(
                            _safe_decimal(row.get("fee"))
                            if row.get("fee") is not None
                            else None
                        ),
                        token_symbol=row.get("token_symbol"),
                    )
                )
                inserted += 1
            session.commit()
        return {"inserted": inserted, "updated": updated, "skipped": skipped}

    def transaction_count(self) -> int:
        with SessionLocal() as session:
            return session.query(models.Transaction).count()

    def list_transactions(
        self,
        address: Optional[str] = None,
        chain: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        with SessionLocal() as session:
            query = session.query(models.Transaction)
            if chain:
                query = query.filter(models.Transaction.chain == chain)
            if address:
                needle = address.lower()
                query = query.filter(
                    (models.Transaction.from_address == needle)
                    | (models.Transaction.to_address == needle)
                )
            query = query.order_by(models.Transaction.block_timestamp)
            if limit is not None:
                query = query.limit(limit)
            rows = query.all()
        return [
            {
                "chain": tx.chain,
                "tx_hash": tx.tx_hash,
                "block_number": tx.block_number,
                "block_timestamp": int(tx.block_timestamp.timestamp())
                if tx.block_timestamp
                else 0,
                "from_address": tx.from_address,
                "to_address": tx.to_address,
                "value": str(tx.value),
                "fee": str(tx.fee) if tx.fee is not None else None,
                "token_symbol": tx.token_symbol,
            }
            for tx in rows
        ]

    def coin_volumes(self, address: str, chain: str) -> Dict:
        needle = address.lower()
        with SessionLocal() as session:
            count = (
                session.query(func.count(models.Transaction.id))
                .filter(
                    models.Transaction.chain == chain,
                    (models.Transaction.from_address == needle)
                    | (models.Transaction.to_address == needle),
                )
                .scalar()
                or 0
            )
            incoming = (
                session.query(func.coalesce(func.sum(models.Transaction.value), 0))
                .filter(
                    models.Transaction.chain == chain,
                    models.Transaction.to_address == needle,
                )
                .scalar()
                or 0
            )
            outgoing = (
                session.query(func.coalesce(func.sum(models.Transaction.value), 0))
                .filter(
                    models.Transaction.chain == chain,
                    models.Transaction.from_address == needle,
                )
                .scalar()
                or 0
            )
        rows = self.list_transactions(address=address, chain=chain, limit=1)
        first_ts = _safe_int(rows[0].get("block_timestamp")) if rows else None
        rows = self.list_transactions(address=address, chain=chain)
        last_ts = _safe_int(rows[-1].get("block_timestamp")) if rows else None
        return {
            "count": count,
            "first_seen": first_ts,
            "last_activity": last_ts,
            "incoming": _safe_decimal(incoming),
            "outgoing": _safe_decimal(outgoing),
        }

    def upsert_summary(self, summary: Dict) -> Dict:
        address = summary.get("address", "").lower()
        chain = summary.get("chain") or "eth"
        with SessionLocal() as session:
            wallet = (
                session.query(models.Wallet)
                .filter(
                    models.Wallet.address == address,
                    models.Wallet.chain == chain,
                )
                .first()
            )
            if wallet is None:
                wallet = models.Wallet(address=address, chain=chain)
                session.add(wallet)
            wallet.transaction_count = _safe_int(summary.get("transaction_count", wallet.transaction_count or 0))
            wallet.incoming_volume = _safe_decimal(summary.get("incoming_volume"))
            wallet.outgoing_volume = _safe_decimal(summary.get("outgoing_volume"))
            if summary.get("balance") is not None:
                wallet.balance = _safe_decimal(summary.get("balance"))
            wallet.risk = summary.get("risk", wallet.risk or "unknown")
            wallet.risk_score = _safe_int(summary.get("risk_score")) if summary.get("risk_score") is not None else wallet.risk_score or 0
            wallet.investigation_status = summary.get(
                "investigation_status", wallet.investigation_status or "analyzed"
            )
            if summary.get("first_seen"):
                wallet.first_seen = datetime.fromtimestamp(_safe_int(summary["first_seen"]), tz=timezone.utc)
            if summary.get("last_activity"):
                wallet.last_activity = datetime.fromtimestamp(_safe_int(summary["last_activity"]), tz=timezone.utc)
            session.commit()
            session.refresh(wallet)
        return {
            "address": address,
            "chain": chain,
            "first_seen": summary.get("first_seen"),
            "last_activity": summary.get("last_activity"),
            "transaction_count": wallet.transaction_count,
            "incoming_volume": str(wallet.incoming_volume),
            "outgoing_volume": str(wallet.outgoing_volume),
            "balance": str(wallet.balance) if wallet.balance is not None else None,
            "risk": wallet.risk,
            "risk_score": wallet.risk_score,
            "investigation_status": wallet.investigation_status,
        }

    def get_summary(self, address: str, chain: str) -> Optional[Dict]:
        with SessionLocal() as session:
            wallet = (
                session.query(models.Wallet)
                .filter(
                    models.Wallet.address == address.lower(),
                    models.Wallet.chain == chain,
                )
                .first()
            )
            if wallet is None:
                return None
        return {
            "address": wallet.address,
            "chain": wallet.chain,
            "first_seen": int(wallet.first_seen.timestamp()) if wallet.first_seen else None,
            "last_activity": int(wallet.last_activity.timestamp()) if wallet.last_activity else None,
            "transaction_count": wallet.transaction_count,
            "incoming_volume": str(wallet.incoming_volume),
            "outgoing_volume": str(wallet.outgoing_volume),
            "balance": str(wallet.balance) if wallet.balance is not None else None,
            "risk": wallet.risk,
            "risk_score": wallet.risk_score,
            "investigation_status": wallet.investigation_status,
        }


_memory_repository: Optional[MemoryWalletRepository] = None


def make_wallet_repository() -> WalletRepository:
    if database_available():
        return DbWalletRepository()
    global _memory_repository
    if _memory_repository is None:
        _memory_repository = MemoryWalletRepository()
    return _memory_repository