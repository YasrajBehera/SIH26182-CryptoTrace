"""Analytical risk assessment module.

Scores are heuristic rankings computed from on-chain activity and attribution
outputs. They are explicitly NOT determinations of criminality or illegality.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from risk.repository import RiskRepository, make_risk_repository


class RiskFactor(BaseModel):
    label: str
    detail: str
    weight: float = Field(0.0, ge=0.0, le=1.0)


class RiskAssessment(BaseModel):
    investigation_id: Optional[str] = None
    wallet_address: str
    chain: str
    level: str = "unknown"
    risk_score: float = 0.0
    summary: str = ""
    reasoning: List[str] = Field(default_factory=list)
    factors: List[RiskFactor] = Field(default_factory=list)
    data_source: str = "analytical_heuristic"
    disclaimer: str = (
        "Analytical risk heuristics only. Not a determination of criminality, "
        "illegality, or ownership."
    )
    created_at: Optional[str] = None


class RiskService:
    def __init__(self, repository: Optional[RiskRepository] = None) -> None:
        self._repo = repository or make_risk_repository()

    @property
    def repository(self) -> RiskRepository:
        return self._repo

    def evaluate(
        self,
        address: str,
        chain: str,
        candidates: List,
        transfers: Optional[List] = None,
        evidence_count: int = 0,
        investigation_id: Optional[str] = None,
    ) -> RiskAssessment:
        """Compute an analytical risk heuristic for a wallet."""
        from datetime import datetime, timezone

        best_score = 0.0
        best_confidence = "LOW"
        has_known_match = False
        for c in candidates:
            if isinstance(c, dict):
                score = float(c.get("score") or 0.0)
                raw_conf = c.get("confidence", "LOW")
                confidence = (
                    raw_conf.value if hasattr(raw_conf, "value") else str(raw_conf)
                )
                breakdown = c.get("score_breakdown") or {}
                known_match = (
                    breakdown.get("known_address_match", 0)
                    if isinstance(breakdown, dict)
                    else 0
                )
            else:
                score = float(getattr(c, "score", 0.0) or 0.0)
                raw_conf = getattr(c, "confidence", None)
                confidence = (
                    raw_conf.value if getattr(raw_conf, "value", None) else "LOW"
                )
                breakdown = getattr(c, "score_breakdown", None)
                known_match = (
                    getattr(breakdown, "known_address_match", 0)
                    if breakdown is not None
                    else 0
                )
            if score > best_score:
                best_score = score
                best_confidence = confidence or "LOW"
            if int(known_match or 0) > 0:
                has_known_match = True

        counterparties = 0
        in_count = 0
        out_count = 0
        for tx in transfers or []:
            if not isinstance(tx, dict):
                continue
            if (tx.get("to_address") or "").lower() == address.lower():
                in_count += 1
                counterparties += 1
            elif (tx.get("from_address") or "").lower() == address.lower():
                out_count += 1
                counterparties += 1

        factors: List[RiskFactor] = []
        reasoning: List[str] = []

        score = 0.0

        # Factor 1: strength of the top attribution candidate (70%).
        f1 = min(best_score / 100.0, 1.0)
        score += 0.70 * f1 * 100.0
        factors.append(
            RiskFactor(
                label="attribution_signal",
                detail=f"Top candidate ranked at {best_score:.0f}/100 "
                f"({best_confidence})",
                weight=0.70,
            )
        )
        if best_score > 0:
            reasoning.append(
                f"Strongest attribution candidate scored {best_score:.0f}/100 "
                f"with {best_confidence} confidence."
            )

        # Factor 2: known-address match (10%).
        f2 = 1.0 if has_known_match else 0.2
        score += 0.10 * f2 * 100.0
        factors.append(RiskFactor(label="known_match", detail=(
            "Direct known-address match present" if has_known_match
            else "No direct known-address match"
        ), weight=0.10))
        reasoning.append(
            "Direct match with a known VASP address." if has_known_match
            else "No direct known-address (VASP) match observed."
        )

        # Factor 3: evidence volume (10%).
        ev_signal = min(60.0, float(evidence_count) * 10.0) / 100.0
        score += 0.10 * ev_signal * 100.0
        factors.append(RiskFactor(
            label="evidence_volume",
            detail=f"{evidence_count} evidence record(s) linked",
            weight=0.10,
        ))

        # Factor 4: counterparty exposure (5%).
        f4 = 0.0
        if counterparties > 20:
            f4 = 0.8
        elif counterparties > 8:
            f4 = 0.6
        elif counterparties > 2:
            f4 = 0.4
        elif counterparties > 0:
            f4 = 0.2
        score += 0.05 * f4 * 100.0
        factors.append(RiskFactor(
            label="counterparty_exposure",
            detail=f"{counterparties} unique counterparty(s) in stored flow",
            weight=0.05,
        ))
        if counterparties > 0:
            reasoning.append(
                f"Wallet connects to {counterparties} counterparty(s) in the "
                "analyzed flow."
            )

        # Factor 5: activity balance (5%).
        f5 = 0.0
        if in_count > 0 and out_count > 0:
            ratio = min(in_count, out_count) / max(in_count, out_count)
            f5 = 0.5 + 0.5 * ratio
        elif (in_count + out_count) > 0:
            f5 = 0.35
        score += 0.05 * f5 * 100.0
        factors.append(RiskFactor(
            label="activity_balance",
            detail=f"{in_count} inbound / {out_count} outbound flows",
            weight=0.05,
        ))

        score = max(0.0, min(100.0, round(score, 2)))
        level = self._level_for(score)
        reasoning.append(
            f"Aggregated analytical risk score: {score:.0f}/100 ({level.upper()})."
        )

        summary = (
            f"Analytical risk for {address} on {chain}: {level.upper()} "
            f"({score:.0f}/100). "
            "Based on attribution signal, known-address matches, evidence "
            "volume, counterparty exposure, and activity balance."
        )

        return RiskAssessment(
            investigation_id=investigation_id,
            wallet_address=address.lower(),
            chain=chain,
            level=level,
            risk_score=score,
            summary=summary,
            reasoning=reasoning,
            factors=factors,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def _level_for(score: float) -> str:
        if score >= 80:
            return "critical"
        if score >= 60:
            return "high"
        if score >= 30:
            return "medium"
        if score >= 10:
            return "low"
        return "unknown"

    def persist(self, assessment: RiskAssessment) -> RiskAssessment:
        self._repo.save(assessment)
        return assessment

    def get_for_investigation(
        self, investigation_id: str
    ) -> Optional[RiskAssessment]:
        return self._repo.get_latest(investigation_id)

    def get_for_wallet(self, address: str, chain: str) -> Optional[RiskAssessment]:
        return self._repo.get_latest_for_wallet(address, chain)