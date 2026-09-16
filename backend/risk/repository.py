"""Risk persistence: SQLAlchemy backend when Postgres is reachable; in-memory
store otherwise."""

from __future__ import annotations

import threading
from typing import Dict, Optional

from app.db import SessionLocal, database_available


def canonical_chain(chain: str) -> str:
    """Map any accepted chain spelling to the canonical identifier used by the
    risk store (the same identifier the frontend sends as ``?chain=``).

    The frontend normalizes ``ethereum`` -> ``eth`` before persisting a case,
    but clients that call the backend directly (harnesses, seeds, scripts) may
    store ``network="ethereum"`` or ``"Ethereum"``. Risk rows are keyed by the
    case network, so without normalization an exact ``chain == "eth"`` lookup
    misses the row even though it exists -> a spurious 404 on read-after-write.
    """
    normalized = (chain or "eth").strip().lower()
    return "eth" if normalized == "ethereum" else normalized


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
                "criminal_intelligence": assessment.criminal_intelligence,
                "signals": [
                    s.model_dump() if not isinstance(s, dict) else s
                    for s in assessment.signals
                ],
                "ml_assessment": assessment.ml_assessment,
                "data_source": assessment.data_source,
                "created_at": assessment.created_at,
            }
            if assessment.investigation_id:
                self._by_investigation[assessment.investigation_id] = record
            self._by_wallet[
                (assessment.wallet_address, canonical_chain(assessment.chain))
            ] = record

    def get_latest(self, investigation_id: str):
        with self._lock:
            record = self._by_investigation.get(investigation_id)
            if record:
                from risk.service import RiskAssessment, RiskFactor, RiskSignal

                return RiskAssessment(
                    **{
                        **record,
                        "factors": [RiskFactor(**f) if not isinstance(f, RiskFactor) else f for f in record["factors"]],
                        "signals": [RiskSignal(**s) if not isinstance(s, RiskSignal) else s for s in record.get("signals") or []],
                    }
                )
            return None

    def get_latest_for_wallet(self, address: str, chain: str):
        with self._lock:
            record = self._by_wallet.get((address.lower(), canonical_chain(chain)))
            if record:
                from risk.service import RiskAssessment, RiskFactor, RiskSignal

                return RiskAssessment(
                    **{
                        **record,
                        "factors": [RiskFactor(**f) if not isinstance(f, RiskFactor) else f for f in record["factors"]],
                        "signals": [RiskSignal(**s) if not isinstance(s, RiskSignal) else s for s in record.get("signals") or []],
                    }
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
                    chain=canonical_chain(assessment.chain),
                    level=assessment.level,
                    risk_score=Decimal(str(assessment.risk_score)),
                    summary=assessment.summary,
                    factors=factor_dicts,
                    criminal_intelligence=assessment.criminal_intelligence,
                    ml_assessment=assessment.ml_assessment,
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
        data = {
            "investigation_id": row.investigation_id,
            "wallet_address": row.wallet_address,
            "chain": row.chain,
            "level": row.level,
            "risk_score": float(row.risk_score),
            "summary": row.summary,
            "reasoning": [],
            "factors": row.factors or [],
            "criminal_intelligence": row.criminal_intelligence,
            "signals": (row.criminal_intelligence or {}).get("signals") or [],
            "ml_assessment": row.ml_assessment,
            "data_source": "analytical_heuristic",
            "created_at": row.created_at.isoformat(),
        }
        return data

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

        from sqlalchemy import func

        canonical = canonical_chain(chain)
        # Accept the canonical identifier and every alias that canonicalizes to
        # the same value (e.g. legacy rows persisted with chain="ethereum" stay
        # readable via ?chain=eth).
        candidates = {
            canonical,
            "ethereum" if canonical in ("eth", "ethereum") else canonical,
        }
        data = self._latest_common(
            lambda m: (m.wallet_address == address.lower())
            & (func.lower(m.chain).in_(candidates))
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