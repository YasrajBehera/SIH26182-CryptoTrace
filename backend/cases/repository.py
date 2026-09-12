"""Investigation persistence: SQLAlchemy/Postgres when available; deterministic
in-memory store otherwise. Both implement the same interface so the service
never cares which one it uses."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.db import SessionLocal, database_available


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _case_id() -> str:
    return f"case-{uuid.uuid4().hex[:8]}"


def _row_to_dict(row) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description or "",
        "primary_wallet": row.primary_wallet,
        "network": row.network or "eth",
        "priority": row.priority or "normal",
        "risk": row.risk or "unknown",
        "status": row.status or "open",
        "latest_analysis_id": row.latest_analysis_id,
        "latest_data_source": row.latest_data_source or "demo",
        "latest_transactions": row.latest_transactions or [],
        "latest_candidates": row.latest_candidates or [],
        "evidence_count": row.evidence_count or 0,
        "assigned_analyst": row.assigned_analyst or "Unassigned",
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else _now_iso(),
        "updated_at": row.updated_at.isoformat() if row.updated_at else _now_iso(),
        "tags": list(row.tags or []),
    }


class InvestigationRepository:
    def create(self, payload: dict) -> dict:
        raise NotImplementedError

    def get(self, case_id: str) -> Optional[dict]:
        raise NotImplementedError

    def list(self, filters: Optional[dict] = None) -> List[dict]:
        raise NotImplementedError

    def update(self, case_id: str, fields: dict) -> Optional[dict]:
        raise NotImplementedError

    def delete(self, case_id: str) -> bool:
        raise NotImplementedError


class MemoryInvestigationRepository(InvestigationRepository):
    is_demo: bool = True

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: Dict[str, dict] = {}

    def create(self, payload: dict) -> dict:
        now = _now_iso()
        record = {
            "id": _case_id(),
            "name": payload.get("name", "Untitled investigation"),
            "description": payload.get("description", ""),
            "primary_wallet": payload.get("primary_wallet", ""),
            "network": payload.get("network", "eth"),
            "priority": payload.get("priority", "normal"),
            "risk": "unknown",
            "status": "open",
            "latest_analysis_id": None,
            "latest_data_source": None,
            "latest_transactions": [],
            "latest_candidates": [],
            "evidence_count": 0,
            "assigned_analyst": payload.get("assigned_analyst", "Unassigned"),
            "created_by": payload.get("created_by", 0),
            "tags": list(payload.get("tags", [])),
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            self._records[record["id"]] = record
        return record

    def get(self, case_id: str) -> Optional[dict]:
        with self._lock:
            record = self._records.get(case_id)
            return dict(record) if record else None

    def list(self, filters: Optional[dict] = None) -> List[dict]:
        filters = filters or {}
        with self._lock:
            items = list(self._records.values())
        status = filters.get("status")
        q = (filters.get("q") or "").lower()
        owner = filters.get("created_by")
        result = []
        for item in items:
            if status and item.get("status") != status:
                continue
            if owner is not None and item.get("created_by") != owner:
                continue
            if q:
                haystack = " ".join([
                    item.get("name", ""),
                    item.get("primary_wallet", ""),
                    item.get("description", ""),
                ]).lower()
                if q not in haystack:
                    continue
            result.append(dict(item))
        result.sort(key=lambda i: i.get("updated_at", ""), reverse=True)
        return result

    def update(self, case_id: str, fields: dict) -> Optional[dict]:
        with self._lock:
            record = self._records.get(case_id)
            if record is None:
                return None
            allowed = {
                "name", "description", "primary_wallet", "network",
                "priority", "risk", "status", "assigned_analyst",
                "latest_analysis_id", "latest_data_source",
                "latest_transactions", "latest_candidates",
                "evidence_count", "tags",
            }
            for key, value in fields.items():
                if key in allowed:
                    record[key] = value
            record["updated_at"] = _now_iso()
            return dict(record)

    def delete(self, case_id: str) -> bool:
        with self._lock:
            return self._records.pop(case_id, None) is not None


class DbInvestigationRepository(InvestigationRepository):
    is_demo: bool = False

    def _row_to_record(self, row) -> dict:
        return _row_to_dict(row)

    def create(self, payload: dict) -> dict:
        from app import models

        with SessionLocal() as session:
            row = models.Investigation(
                id=_case_id(),
                name=payload.get("name", "Untitled investigation"),
                description=payload.get("description", ""),
                primary_wallet=payload.get("primary_wallet", ""),
                network=payload.get("network", "eth"),
                priority=payload.get("priority", "normal"),
                assigned_analyst=payload.get("assigned_analyst", "Unassigned"),
                created_by=payload.get("created_by", 0),
                tags=list(payload.get("tags", [])),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._row_to_record(row)

    def get(self, case_id: str) -> Optional[dict]:
        from app import models

        with SessionLocal() as session:
            row = (
                session.query(models.Investigation)
                .filter(models.Investigation.id == case_id)
                .first()
            )
            return self._row_to_record(row) if row else None

    def list(self, filters: Optional[dict] = None) -> List[dict]:
        from app import models

        filters = filters or {}
        with SessionLocal() as session:
            query = session.query(models.Investigation)
            status = filters.get("status")
            owner = filters.get("created_by")
            q = (filters.get("q") or "").lower()
            if status:
                query = query.filter(models.Investigation.status == status)
            if owner is not None:
                query = query.filter(models.Investigation.created_by == owner)
            if q:
                query = query.filter(
                    (models.Investigation.name.ilike(f"%{q}%"))
                    | (models.Investigation.primary_wallet.ilike(f"%{q}%"))
                )
            rows = query.order_by(models.Investigation.updated_at.desc()).all()
            return [self._row_to_record(r) for r in rows]

    def update(self, case_id: str, fields: dict) -> Optional[dict]:
        from app import models

        allowed = {
            "name", "description", "primary_wallet", "network",
            "priority", "risk", "status", "assigned_analyst",
            "latest_analysis_id", "latest_data_source",
            "latest_transactions", "latest_candidates",
            "evidence_count", "tags",
        }
        with SessionLocal() as session:
            row = (
                session.query(models.Investigation)
                .filter(models.Investigation.id == case_id)
                .first()
            )
            if row is None:
                return None
            for key, value in fields.items():
                if key in allowed:
                    setattr(row, key, value)
            row.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(row)
            return self._row_to_record(row)

    def delete(self, case_id: str) -> bool:
        from app import models

        with SessionLocal() as session:
            deleted = (
                session.query(models.Investigation)
                .filter(models.Investigation.id == case_id)
                .delete()
            )
            session.commit()
            return deleted > 0


_memory_repository: Optional[MemoryInvestigationRepository] = None
_db_investigation_repository: Optional[DbInvestigationRepository] = None


def make_investigation_repository() -> InvestigationRepository:
    global _db_investigation_repository, _memory_repository
    if database_available():
        if _db_investigation_repository is None:
            _db_investigation_repository = DbInvestigationRepository()
        return _db_investigation_repository
    if _memory_repository is None:
        _memory_repository = MemoryInvestigationRepository()
    return _memory_repository