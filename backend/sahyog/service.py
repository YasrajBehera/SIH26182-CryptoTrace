"""SAHYOG referral service: ingest, triage heuristics, and handoff to a
CryptoTrace investigation. The flow is explicitly DEMO (no live SAHYOG
connection); nothing is presented as live LE-intake data."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sahyog.models import (
    HandoffRequest,
    SahyogReferralCreate,
    SahyogReferralOut,
    TriageRequest,
    TriageResult,
)
from sahyog.repository import SahyogRepository, make_sahyog_repository


class SahyogReferralNotFoundError(Exception):
    pass


class SahyogChainNotSupportedError(Exception):
    pass


class SahyogService:
    def __init__(self, repository: Optional[SahyogRepository] = None) -> None:
        self._repo = repository or make_sahyog_repository()

    def list(self, status: Optional[str] = None) -> list:
        return [self._to_out(r) for r in self._repo.list(status)]

    def get(self, referral_id: str) -> SahyogReferralOut:
        record = self._repo.get(referral_id)
        if record is None:
            raise SahyogReferralNotFoundError(referral_id)
        return self._to_out(record)

    def ingest(self, payload: SahyogReferralCreate) -> SahyogReferralOut:
        record = self._repo.create(payload.model_dump())
        return self._to_out(record)

    def triage(
        self, referral_id: str, request: TriageRequest, user
    ) -> SahyogReferralOut:
        record = self._repo.get(referral_id)
        if record is None:
            raise SahyogReferralNotFoundError(referral_id)

        prior_flags = sum(
            1
            for r in self._repo.list(None)
            if r["id"] != referral_id
            and (r.get("suspect_wallet") or "").lower()
            == (record.get("suspect_wallet") or "").lower()
        )

        heuristics = self._heuristic_triage(record, prior_flags)

        triage = TriageResult(
            risk=request.risk or heuristics.risk,
            wallet_age_months=(
                request.wallet_age_months
                if request.wallet_age_months is not None
                else heuristics.wallet_age_months
            ),
            exchange_exposed=(
                request.exchange_exposed
                if request.exchange_exposed is not None
                else heuristics.exchange_exposed
            ),
            prior_flags=(
                request.prior_flags
                if request.prior_flags is not None
                else prior_flags
            ),
            recommendation=request.recommendation or heuristics.recommendation,
            triaged_by=user.username if hasattr(user, "username") else str(user),
            triaged_at=datetime.now(timezone.utc).isoformat(),
        )

        updated = self._repo.update(
            referral_id,
            {"status": "triaged", "triage": triage.model_dump()},
        )
        return self._to_out(updated)

    def handoff(
        self,
        referral_id: str,
        request: HandoffRequest,
        user,
        investigation_service,
    ) -> SahyogReferralOut:
        record = self._repo.get(referral_id)
        if record is None:
            raise SahyogReferralNotFoundError(referral_id)

        chain = record.get("chain", "eth")
        if chain != "eth":
            raise SahyogChainNotSupportedError(
                "Handoff to a CryptoTrace investigation currently supports "
                "Ethereum (0x...) suspect wallets only."
            )

        from cases.models import InvestigationCreate
        from cases.service import InvestigationService

        svc = investigation_service or InvestigationService()
        case = svc.create(
            InvestigationCreate(
                name=request.case_name or f"SAHYOG {record.get('fir_no')}",
                description=filtered_description(record, request.description),
                primary_wallet=record.get("suspect_wallet", "").lower(),
                network="eth",
                priority=request.priority,
                tags=["sahyog"],
            ),
            user,
        )

        updated = self._repo.update(
            referral_id,
            {"status": "handed_off", "handoff_case_id": case.id},
        )
        return self._to_out(updated)

    def _heuristic_triage(
        self, record: dict, prior_flags: int
    ) -> TriageResult:
        amount = float(record.get("amount_usdt", 0.0))
        risk = "low"
        recommendation = "Low priority; monitor the suspect wallet."
        if amount >= 1_000_000:
            risk = "high"
            recommendation = (
                "High value referral; recommend immediate on-chain analysis "
                "and exchange query escalation."
            )
        elif amount >= 100_000:
            risk = "medium"
            recommendation = (
                "Moderate value referral; recommend on-chain analysis via "
                "CryptoTrace investigation."
            )
        if prior_flags > 0:
            recommendation += (
                " Multiple referrals reference this same suspect wallet; "
                "consider consolidation."
            )
        return TriageResult(
            risk=risk,
            wallet_age_months=0.0,
            exchange_exposed=False,
            prior_flags=prior_flags,
            recommendation=recommendation,
            triaged_by="",
            triaged_at="",
        )

    def _to_out(self, record: dict) -> SahyogReferralOut:
        return SahyogReferralOut(
            id=record.get("id", ""),
            fir_no=record.get("fir_no", ""),
            reported_at=record.get("reported_at"),
            victim_name=record.get("victim_name", ""),
            amount_usdt=float(record.get("amount_usdt", 0.0)),
            suspect_wallet=record.get("suspect_wallet", ""),
            chain=record.get("chain", "eth"),
            status=record.get("status", "new"),
            triage=record.get("triage"),
            handoff_case_id=record.get("handoff_case_id"),
            data_source=record.get("data_source", "demo"),
        )


def filtered_description(record: dict, description: Optional[str]) -> str:
    base = (
        description
        or f"Referral {record.get('fir_no')} for victim "
        f"{record.get('victim_name')} (USDT {record.get('amount_usdt')})."
    )
    return base