"""Evidence repositories: durable SQLAlchemy backend when Postgres is
reachable; a deterministic in-memory store otherwise (offline tests/demos).

The memory implementation keeps the ``EvidenceRepository`` name for backward
compatibility with existing tests; both implementations satisfy the same
interface so the EvidenceService never cares which store it uses.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from app.db import SessionLocal, database_available
from evidence.models import EvidenceRecord, Provenance


def _record_from_row(row) -> EvidenceRecord:
    graph_path = list(row.graph_path) if row.graph_path else None
    return EvidenceRecord(
        evidence_id=row.evidence_id,
        attribution_id=row.attribution_id,
        investigation_id=row.investigation_id,
        evidence_type=row.evidence_type,
        address=row.address,
        chain=row.chain,
        tx_hash=row.tx_hash,
        graph_path=graph_path,
        source=row.source,
        timestamp=row.timestamp,
        confidence=row.confidence,
        description=row.description,
        provenance=Provenance(**row.provenance) if row.provenance else Provenance(
            created_at="", method="unknown"
        ),
    )


def _row_from_record(record: EvidenceRecord) -> dict:
    return {
        "evidence_id": record.evidence_id,
        "attribution_id": record.attribution_id,
        "investigation_id": record.investigation_id,
        "evidence_type": record.evidence_type.value,
        "address": record.address,
        "chain": record.chain,
        "tx_hash": record.tx_hash,
        "graph_path": list(record.graph_path) if record.graph_path else None,
        "source": record.source,
        "timestamp": record.timestamp,
        "confidence": record.confidence,
        "description": record.description,
        "provenance": record.provenance.model_dump() if record.provenance else None,
    }


class EvidenceRepository:
    """In-memory store (the compatible default used by tests and demos)."""

    is_demo: bool = True

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: Dict[str, EvidenceRecord] = {}
        self._by_attribution: Dict[str, List[str]] = {}
        self._by_address: Dict[str, List[str]] = {}
        self._by_investigation: Dict[str, List[str]] = {}

    def store(self, record: EvidenceRecord) -> None:
        with self._lock:
            self._records[record.evidence_id] = record
            self._by_attribution.setdefault(record.attribution_id, []).append(
                record.evidence_id
            )
            addr_key = f"{record.address.lower()}:{record.chain}"
            self._by_address.setdefault(addr_key, []).append(record.evidence_id)
            if record.investigation_id:
                self._by_investigation.setdefault(
                    record.investigation_id, []
                ).append(record.evidence_id)

    def get(self, evidence_id: str) -> Optional[EvidenceRecord]:
        with self._lock:
            return self._records.get(evidence_id)

    def get_by_attribution(self, attribution_id: str) -> List[EvidenceRecord]:
        with self._lock:
            ids = self._by_attribution.get(attribution_id, [])
            return [self._records[eid] for eid in ids if eid in self._records]

    def get_by_address(self, address: str, chain: str) -> List[EvidenceRecord]:
        addr_key = f"{address.lower()}:{chain}"
        with self._lock:
            ids = self._by_address.get(addr_key, [])
            return [self._records[eid] for eid in ids if eid in self._records]

    def get_by_investigation(self, investigation_id: str) -> List[EvidenceRecord]:
        with self._lock:
            ids = self._by_investigation.get(investigation_id, [])
            return [self._records[eid] for eid in ids if eid in self._records]

    def delete(self, evidence_id: str) -> bool:
        with self._lock:
            record = self._records.pop(evidence_id, None)
            if record is None:
                return False
            if record.attribution_id in self._by_attribution:
                try:
                    self._by_attribution[record.attribution_id].remove(evidence_id)
                except ValueError:
                    pass
            addr_key = f"{record.address.lower()}:{record.chain}"
            if addr_key in self._by_address:
                try:
                    self._by_address[addr_key].remove(evidence_id)
                except ValueError:
                    pass
            if record.investigation_id and record.investigation_id in self._by_investigation:
                try:
                    self._by_investigation[record.investigation_id].remove(evidence_id)
                except ValueError:
                    pass
            return True

    def count(self) -> int:
        with self._lock:
            return len(self._records)


class DbEvidenceRepository:
    """SQLAlchemy/Postgres-backed evidence store."""

    is_demo: bool = False

    def store(self, record: EvidenceRecord) -> None:
        from app import models

        with SessionLocal() as session:
            existing = (
                session.query(models.Evidence)
                .filter(models.Evidence.evidence_id == record.evidence_id)
                .first()
            )
            data = _row_from_record(record)
            if existing:
                for key, value in data.items():
                    setattr(existing, key, value)
                session.commit()
                return
            session.add(models.Evidence(**data))
            session.commit()

    def get(self, evidence_id: str) -> Optional[EvidenceRecord]:
        from app import models

        with SessionLocal() as session:
            row = (
                session.query(models.Evidence)
                .filter(models.Evidence.evidence_id == evidence_id)
                .first()
            )
            return _record_from_row(row) if row else None

    def get_by_attribution(self, attribution_id: str) -> List[EvidenceRecord]:
        from app import models

        with SessionLocal() as session:
            rows = (
                session.query(models.Evidence)
                .filter(models.Evidence.attribution_id == attribution_id)
                .order_by(models.Evidence.id)
                .all()
            )
            return [_record_from_row(r) for r in rows]

    def get_by_address(self, address: str, chain: str) -> List[EvidenceRecord]:
        from app import models

        with SessionLocal() as session:
            rows = (
                session.query(models.Evidence)
                .filter(
                    models.Evidence.address == address.lower(),
                    models.Evidence.chain == chain,
                )
                .order_by(models.Evidence.id)
                .all()
            )
            return [_record_from_row(r) for r in rows]

    def get_by_investigation(self, investigation_id: str) -> List[EvidenceRecord]:
        from app import models

        with SessionLocal() as session:
            rows = (
                session.query(models.Evidence)
                .filter(models.Evidence.investigation_id == investigation_id)
                .order_by(models.Evidence.id)
                .all()
            )
            return [_record_from_row(r) for r in rows]

    def delete(self, evidence_id: str) -> bool:
        from app import models

        with SessionLocal() as session:
            deleted = (
                session.query(models.Evidence)
                .filter(models.Evidence.evidence_id == evidence_id)
                .delete()
            )
            session.commit()
            return deleted > 0

    def count(self) -> int:
        from app import models

        with SessionLocal() as session:
            return session.query(models.Evidence).count()


_db_repository: Optional[DbEvidenceRepository] = None


def make_evidence_repository():
    """Fresh in-memory stores per call (test isolation); a single shared DB store.

    The DB store is intentionally THREAD-SAFE via its own short-lived
    sessions, and sharing it is safe because each method opens its own
    ``SessionLocal``.
    """
    global _db_repository
    if database_available():
        if _db_repository is None:
            _db_repository = DbEvidenceRepository()
        return _db_repository
    return EvidenceRepository()