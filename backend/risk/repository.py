"""Risk persistence: SQLAlchemy backend when Postgres is reachable; in-memory
store otherwise."""

from __future__ import annotations

import threading
from typing import Dict, Optional

from app.db import SessionLocal, database_available


class RiskRepository:
    is_demo: bool = True

    def save(self, assessment) -> None:
        """Persist a risk assessment (pydantic RiskAssessment)."""
        raise NotImplementedError

    def get_latest(self, investigation_id: str):
        raise NotImplementedError

    def get_latest_for_wallet(self, address: str, chain: str):
        raise NotImplementedError


class MemoryRiskRepository(RiskRepository):
    is_demo = True

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_investigation: Dict[str, dict] = {}
        self._by_wallet: Dict[tuple, dict] = {}

    def save(self, assessment) -> None:
        with self._lock:
            record = {
                "investigation_id": assessment.investigation_id,
                "wallet_address": assessment.wallet_address,
                "chain": assessment.chain,
                "level": assessment.level,
                "risk_score": float(assessment.risk_score),
                "summary": assessment.summary,
                "reasoning": list(assessment.reasoning),
                "factors": assessment.factors,
                "data_source": assessment.data_source,
                "created_at": assessment.created_at,
            }
            if assessment.investigation_id:
                self._by_investigation[assessment.investigation_id] = record
            self._by_wallet[(assessment.wallet_address, assessment.chain)] = record

    def get_latest(self, investigation_id: str):
        with self._lock:
            record = self._by_investigation.get(investigation_id)
            if record:
                from risk.service import RiskAssessment, RiskFactor

                return RiskAssessment(
                    **{**record, "factors": [RiskFactor(**f) if not isinstance(f, RiskFactor) else f for f in record["factors"]]}
                )
            return None

    def get_latest_for_wallet(self, address: str, chain: str):
        with self._lock:
            record = self._by_wallet.get((address.lower(), chain))
            if record:
                from risk.service import RiskAssessment, RiskFactor

                return RiskAssessment(
                    **{**record, "factors": [RiskFactor(**f) if not isinstance(f, RiskFactor) else f for f in record["factors"]]}
                )
            return None


class DbRiskRepository(RiskRepository):
    is_demo = False

    def save(self, assessment) -> None:
        from decimal import Decimal

        from app import models

        factor_dicts = [
            f.model_dump() if hasattr(f, "model_dump") else dict(f)
            for f in assessment.factors
        ]
        with SessionLocal() as session:
            session.add(
                models.RiskAssessment(
                    investigation_id=assessment.investigation_id,
                    wallet_address=assessment.wallet_address,
                    chain=assessment.chain,
                    level=assessment.level,
                    risk_score=Decimal(str(assessment.risk_score)),
                    summary=assessment.summary,
                    factors=factor_dicts,
                )
            )
            session.commit()

    def _latest_common(self, query_filter) -> Optional[dict]:
        from app import models

        with SessionLocal() as session:
            row = (
                session.query(models.RiskAssessment)
                .filter(query_filter(models.RiskAssessment))
                .order_by(models.RiskAssessment.created_at.desc())
                .first()
            )
            if row is None:
                return None
        return {
            "investigation_id": row.investigation_id,
            "wallet_address": row.wallet_address,
            "chain": row.chain,
            "level": row.level,
            "risk_score": float(row.risk_score),
            "summary": row.summary,
            "reasoning": [],
            "factors": row.factors or [],
            "data_source": "analytical_heuristic",
            "created_at": row.created_at.isoformat(),
        }

    def get_latest(self, investigation_id: str):
        from risk.service import RiskAssessment

        data = self._latest_common(
            lambda m: m.investigation_id == investigation_id
        )
        if data is None:
            return None
        return RiskAssessment(**data)

    def get_latest_for_wallet(self, address: str, chain: str):
        from risk.service import RiskAssessment

        data = self._latest_common(
            lambda m: (m.wallet_address == address.lower()) & (m.chain == chain)
        )
        if data is None:
            return None
        return RiskAssessment(**data)


_memory_repository: Optional[MemoryRiskRepository] = None
_db_risk_repository: Optional[DbRiskRepository] = None


def make_risk_repository() -> RiskRepository:
    global _db_risk_repository, _memory_repository
    if database_available():
        if _db_risk_repository is None:
            _db_risk_repository = DbRiskRepository()
        return _db_risk_repository
    if _memory_repository is None:
        _memory_repository = MemoryRiskRepository()
    return _memory_repository