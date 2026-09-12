"""SAHYOG referral persistence: SQLAlchemy backend when Postgres is reachable;
deterministic in-memory store otherwise."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.db import SessionLocal, database_available


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row) -> dict:
    return {
        "id": row.id,
        "fir_no": row.fir_no,
        "reported_at": (
            row.reported_at.isoformat() if row.reported_at else None
        ),
        "victim_name": row.victim_name,
        "amount_usdt": float(row.amount_usdt),
        "suspect_wallet": row.suspect_wallet,
        "chain": row.chain or "eth",
        "status": row.status or "new",
        "triage": row.triage,
        "handoff_case_id": row.handoff_case_id,
        "data_source": "postgres",
    }


class SahyogRepository:
    def list(self, status: Optional[str] = None) -> List[dict]:
        raise NotImplementedError

    def get(self, referral_id: str) -> Optional[dict]:
        raise NotImplementedError

    def create(self, payload: dict) -> dict:
        raise NotImplementedError

    def update(self, referral_id: str, fields: dict) -> Optional[dict]:
        raise NotImplementedError


class MemorySahyogRepository(SahyogRepository):
    is_demo: bool = True

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: Dict[str, dict] = {}
        self._seq = 0

    def _next_id(self) -> str:
        self._seq += 1
        return f"sy-{self._seq:04d}"

    def list(self, status: Optional[str] = None) -> List[dict]:
        with self._lock:
            items = list(self._records.values())
        if status:
            items = [r for r in items if r.get("status") == status]
        items.sort(key=lambda r: r.get("reported_at") or "", reverse=True)
        return [dict(r) for r in items]

    def get(self, referral_id: str) -> Optional[dict]:
        with self._lock:
            record = self._records.get(referral_id)
            return dict(record) if record else None

    def create(self, payload: dict) -> dict:
        record = {
            "id": self._next_id(),
            "fir_no": payload.get("fir_no", ""),
            "reported_at": payload.get("reported_at") or _now_iso(),
            "victim_name": payload.get("victim_name", ""),
            "amount_usdt": float(payload.get("amount_usdt", 0.0)),
            "suspect_wallet": payload.get("suspect_wallet", ""),
            "chain": payload.get("chain", "eth"),
            "status": "new",
            "triage": None,
            "handoff_case_id": None,
            "data_source": "demo",
        }
        with self._lock:
            self._records[record["id"]] = record
        return dict(record)

    def update(self, referral_id: str, fields: dict) -> Optional[dict]:
        allowed = {"status", "triage", "handoff_case_id", "fir_no", "victim_name"}
        with self._lock:
            record = self._records.get(referral_id)
            if record is None:
                return None
            for key, value in fields.items():
                if key in allowed:
                    record[key] = value
            return dict(record)


class DbSahyogRepository(SahyogRepository):
    is_demo: bool = False

    def list(self, status: Optional[str] = None) -> List[dict]:
        from app import models

        with SessionLocal() as session:
            query = session.query(models.SahyogReferral)
            if status:
                query = query.filter(models.SahyogReferral.status == status)
            rows = query.order_by(models.SahyogReferral.created_at.desc()).all()
            return [_row_to_dict(r) for r in rows]

    def get(self, referral_id: str) -> Optional[dict]:
        from app import models

        with SessionLocal() as session:
            row = (
                session.query(models.SahyogReferral)
                .filter(models.SahyogReferral.id == referral_id)
                .first()
            )
            return _row_to_dict(row) if row else None

    def create(self, payload: dict) -> dict:
        from app import models

        from decimal import Decimal

        referral_id = f"sy-{uuid.uuid4().hex[:8]}"
        with SessionLocal() as session:
            row = models.SahyogReferral(
                id=referral_id,
                fir_no=payload.get("fir_no", ""),
                reported_at=datetime.now(timezone.utc),
                victim_name=payload.get("victim_name", ""),
                amount_usdt=Decimal(str(payload.get("amount_usdt", 0.0))),
                suspect_wallet=payload.get("suspect_wallet", ""),
                chain=payload.get("chain", "eth"),
                status="new",
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _row_to_dict(row)

    def update(self, referral_id: str, fields: dict) -> Optional[dict]:
        from app import models

        allowed = {"status", "triage", "handoff_case_id", "fir_no", "victim_name"}
        with SessionLocal() as session:
            row = (
                session.query(models.SahyogReferral)
                .filter(models.SahyogReferral.id == referral_id)
                .first()
            )
            if row is None:
                return None
            for key, value in fields.items():
                if key in allowed:
                    setattr(row, key, value)
            session.commit()
            session.refresh(row)
            return _row_to_dict(row)


_memory_repository: Optional[MemorySahyogRepository] = None
_db_repository: Optional[DbSahyogRepository] = None


def make_sahyog_repository() -> SahyogRepository:
    global _memory_repository, _db_repository
    if database_available():
        if _db_repository is None:
            _db_repository = DbSahyogRepository()
        return _db_repository
    if _memory_repository is None:
        _memory_repository = MemorySahyogRepository()
    return _memory_repository