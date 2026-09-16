"""Analytical risk assessment module.

Scores are heuristic rankings computed from on-chain activity and attribution
outputs. They are explicitly NOT determinations of criminality or illegality.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from intelligence.sanctions_service import sanctions_evidence_id
from risk.repository import RiskRepository, make_risk_repository


class RiskFactor(BaseModel):
    label: str
    detail: str
    weight: float = Field(0.0, ge=0.0, le=1.0)


class RiskSignal(BaseModel):
    """One explainable criminal/sanctions signal.

    Signals are only ever assigned when evidence exists; a signal is never
    fabricated and the framework never says "not criminal" for a wallet with
    no match — the absence of a signal means NOT ASSESSED.
    """

    name: str
    detail: str
    source: str = "curated_public_intelligence"
    confidence: str = "HIGH"


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
    # SEPARATE criminal/sanctions intelligence block. Lives on its own field so
    # it can never be confused with — or merged into — the analytical VASP /
    # activity score above. None when no exact match was found (UNKNOWN /
    # NOT ASSESSED), which is not a claim of innocence.
    criminal_intelligence: Optional[dict] = None
    signals: List[RiskSignal] = Field(default_factory=list)
    # SEPARATE ML suspicious-wallet block. Lives on its own field so it can
    # never be confused with the VASP attribution score or the criminal /
    # sanctions intelligence. Always present (status reflects the deployed
    # artifact: trained | not_trained | unavailable); a missing required
    # feature yields UNKNOWN / NOT ASSESSED — never an imputed probability.
    ml_assessment: Optional[dict] = None
    created_at: Optional[str] = None


class RiskService:
    def __init__(
        self,
        repository: Optional[RiskRepository] = None,
        sanctions=None,
        ml_service=None,
    ) -> None:
        self._repo = repository or make_risk_repository()
        if sanctions is None:
            from intelligence.sanctions_service import SanctionsIntelligenceService

            sanctions = SanctionsIntelligenceService()
        self._sanctions = sanctions
        if ml_service is None:
            from ml.service import MLRiskService

            ml_service = MLRiskService()
        self._ml = ml_service

    @property
    def repository(self) -> RiskRepository:
        return self._repo

    @property
    def sanctions(self):
        return self._sanctions

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

        # ---- SEPARATE criminal / sanctions intelligence ----------------- #
        # An exact match in the curated public sanctions/illicit directory is
        # its own, explainable risk determination. It overrides the overall
        # level to HIGH but NEVER changes the analytical risk_score above (a
        # VASP association score of 15.5 stays 15.5 — it does not become 90).
        record = self._sanctions.lookup(address, chain)
        criminal_intelligence = None
        signals: List[RiskSignal] = []
        if record is not None:
            signals = self._sanctions_signals_for(record, address, chain)
            level = "high"
            criminal_intelligence = {
                "level": "high",
                "status": "exact_sanctions_match",
                "reason": (
                    "Exact address match against curated public "
                    "sanctions/illicit intelligence."
                ),
                "entity": record.entity,
                "source": record.source,
                "match_type": record.match_type,
                "confidence": record.confidence,
                "source_type": record.source_type,
                "provenance_source_type": "curated_public_intelligence",
                "evidence_id": sanctions_evidence_id(address, chain),
                "signals": [s.model_dump() for s in signals],
                "disclaimer": (
                    "Curated public intelligence (not a live OFAC integration). "
                    "The address matches a curated public sanctions/illicit "
                    "intelligence record; this is an investigative signal that "
                    "must be independently verified."
                ),
            }
            reasoning.append(
                f"Criminal/sanctions intelligence: exact match in the curated "
                f"public intelligence directory (entity {record.entity}, source "
                f"{record.source}, confidence {record.confidence})."
            )
        else:
            reasoning.append(
                "Criminal/sanctions intelligence: no exact match in the curated "
                "public intelligence directory. Level UNKNOWN / NOT ASSESSED — "
                "absence of a match is not evidence that the wallet is lawful."
            )

        reasoning.append(
            f"Aggregated analytical risk score: {score:.0f}/100 ({level.upper()})."
        )

        # ---- SEPARATE ML suspicious-wallet block -------------------------- #
        # A third signal, independent of both the analytical VASP score and the
        # criminal/sanctions block. Always present: status tells the caller
        # whether a real artifact exists (trained), is absent (not_trained),
        # or could not produce a probability for this wallet (unavailable ->
        # UNKNOWN / NOT ASSESSED). Missing features are reported, never imputed.
        ml_assessment = self._ml.assess(address, chain, transfers or [])
        if ml_assessment.get("status") == "trained" and ml_assessment.get("probability") is not None:
            reasoning.append(
                "ML suspicious-wallet model: "
                f"{ml_assessment.get('wording')} (model "
                f"{ml_assessment.get('model_version')}, dataset "
                f"{ml_assessment.get('dataset_version')})."
            )
        elif ml_assessment.get("status") == "unavailable":
            reasoning.append(
                "ML suspicious-wallet model: UNKNOWN / NOT ASSESSED — required "
                "features could not be computed from on-chain data "
                f"(missing: {', '.join(ml_assessment.get('missing_features', []))}). "
                "No values were imputed."
            )
        else:
            reasoning.append(ml_assessment.get("explanation") or "")

        summary = (
            f"Analytical risk for {address} on {chain}: {level.upper()} "
            f"({score:.0f}/100 analytical heuristic). "
            "Based on attribution signal, known-address matches, evidence "
            "volume, counterparty exposure, and activity balance."
        )
        if record is not None:
            summary += (
                f" Criminal/sanctions intelligence: HIGH — exact match against "
                f"curated public intelligence (entity {record.entity}, source "
                f"{record.source}). Investigative signal; verify independently."
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
            criminal_intelligence=criminal_intelligence,
            signals=signals,
            ml_assessment=ml_assessment,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def _sanctions_signals_for(
        self, record, address: str, chain: str
    ) -> List[RiskSignal]:
        """Explainable criminal/sanctions signals. Only signals with actual
        evidence are produced; nothing is fabricated."""
        return [
            RiskSignal(
                name="sanctions_exact_address_match",
                detail=(
                    "Full canonical address matches a curated public "
                    "sanctions/illicit intelligence record."
                ),
                source=self._sanctions_source_label(record),
                confidence=record.confidence,
            ),
            RiskSignal(
                name="known_illicit_entity_attribution",
                detail=(
                    f"Exact address match is publicly associated with "
                    f"'{record.entity}'."
                ),
                source=self._sanctions_source_label(record),
                confidence=record.confidence,
            ),
        ]

    @staticmethod
    def _sanctions_source_label(record) -> str:
        return "curated_public_intelligence"

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