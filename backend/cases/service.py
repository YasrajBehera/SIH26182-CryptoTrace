"""Investigation service: business rules, ownership scoping, and the
apply-analysis flow that attaches live analysis output to a persisted case."""

from __future__ import annotations

from typing import List, Optional

from cases.models import (
    InvestigationCreate,
    InvestigationListResponse,
    InvestigationOut,
    InvestigationUpdate,
)
from cases.repository import InvestigationRepository, make_investigation_repository
from evidence.service import EvidenceService
from risk.repository import RiskRepository
from risk.service import RiskService
from wallets.repository import WalletRepository
from wallets.service import WalletService

_ADMIN_ROLES = {"admin", "senior_investigator"}


class CaseNotFoundError(Exception):
    pass


class CaseAccessError(Exception):
    pass


class CaseConflictError(Exception):
    pass


class InvestigationService:
    def __init__(
        self,
        repository: Optional[InvestigationRepository] = None,
        evidence_service: Optional[EvidenceService] = None,
        wallet_repository: Optional[WalletRepository] = None,
        risk_repository: Optional[RiskRepository] = None,
    ) -> None:
        self._repo = repository or make_investigation_repository()
        self._evidence = evidence_service or EvidenceService()
        self._wallet_service = WalletService(repository=wallet_repository)
        self._risk_service = RiskService(repository=risk_repository)

    @property
    def is_persistent(self) -> bool:
        return not getattr(self._repo, "is_demo", True)

    def _can_read(self, case: dict, user) -> bool:
        if user.role in _ADMIN_ROLES:
            return True
        return case.get("created_by") == user.id

    def _can_write(self, case: dict, user) -> bool:
        if user.role in _ADMIN_ROLES:
            return True
        return case.get("created_by") == user.id

    def _require_case(self, case_id: str, user) -> dict:
        case = self._repo.get(case_id)
        if case is None:
            raise CaseNotFoundError(case_id)
        if not self._can_read(case, user):
            raise CaseNotFoundError(case_id)
        return case

    def create(self, payload: InvestigationCreate, user) -> InvestigationOut:
        record = self._repo.create(
            {
                "name": payload.name,
                "description": payload.description,
                "primary_wallet": payload.primary_wallet.lower(),
                "network": payload.network,
                "priority": payload.priority,
                "created_by": user.id,
                "tags": list(payload.tags),
            }
        )
        return self._to_out(record)

    def list(
        self,
        user,
        status: Optional[str] = None,
        q: Optional[str] = None,
        owner_only: bool = True,
    ) -> InvestigationListResponse:
        filters = {"status": status, "q": q}
        if owner_only and user.role not in _ADMIN_ROLES:
            filters["created_by"] = user.id
        records = self._repo.list(filters)
        return InvestigationListResponse(
            investigations=[self._to_out(r) for r in records],
            total=len(records),
            source="postgres" if not getattr(self._repo, "is_demo", True) else "memory",
        )

    def get(self, case_id: str, user) -> InvestigationOut:
        case = self._require_case(case_id, user)
        return self._to_out(case)

    def update(
        self, case_id: str, payload: InvestigationUpdate, user
    ) -> InvestigationOut:
        case = self._require_case(case_id, user)
        if not self._can_write(case, user):
            raise CaseAccessError(case_id)
        changes = payload.model_dump(exclude_unset=True)
        if "primary_wallet" in changes:
            changes["primary_wallet"] = changes["primary_wallet"].lower()
        record = self._repo.update(case_id, changes)
        return self._to_out(record)

    def delete(self, case_id: str, user) -> bool:
        case = self._require_case(case_id, user)
        if not self._can_write(case, user):
            raise CaseAccessError(case_id)
        return self._repo.delete(case_id)

    def apply_analysis(
        self,
        case_id: str,
        address: str,
        analysis_id: str,
        data_source: str,
        candidates: Optional[List[dict]] = None,
        transactions: Optional[List[dict]] = None,
        user=None,
    ) -> InvestigationOut:
        case = self._require_case(case_id, user)
        if not self._can_write(case, user):
            raise CaseAccessError(case_id)
        if case.get("primary_wallet", "").lower() != address.lower():
            raise CaseConflictError(
                f"Wallets differ: case {case_id} tracks "
                f"{case.get('primary_wallet')}, analysis ran on {address}"
            )

        # Link produced evidence to this case (the evidence service keeps them
        # keyed by the attribution / analysis id).
        records = self._evidence.link_to_investigation(analysis_id, case_id)
        evidence_count = len(records)

        # Evaluate analytical risk first so the wallet summary can carry it.
        assessment = self._risk_service.evaluate(
            address=address,
            chain=case.get("network", "eth"),
            candidates=candidates or [],
            transfers=transactions or [],
            evidence_count=evidence_count,
            investigation_id=case_id,
        )
        self._risk_service.persist(assessment)

        # Persist the flow into the wallet store and refresh summaries.
        self._wallet_service.register_analysis(
            address=address,
            chain=case.get("network", "eth"),
            transfers=transactions or [],
            risk=assessment.level,
            risk_score=int(assessment.risk_score),
        )

        record = self._repo.update(
            case_id,
            {
                "latest_analysis_id": analysis_id,
                "latest_data_source": data_source,
                "latest_transactions": transactions or [],
                "latest_candidates": candidates or [],
                "evidence_count": evidence_count,
                "risk": assessment.level,
                "status": "investigating",
            },
        )
        return self._to_out(record)

    def risk_for(self, case_id: str, user):
        case = self._require_case(case_id, user)
        latest = self._risk_service.get_for_investigation(case_id)
        if latest is not None:
            return latest
        return self._risk_service.evaluate(
            address=case.get("primary_wallet", ""),
            chain=case.get("network", "eth"),
            candidates=case.get("latest_candidates") or [],
            transfers=case.get("latest_transactions") or [],
            evidence_count=case.get("evidence_count", 0),
            investigation_id=case_id,
        )

    def _to_out(self, record: dict) -> InvestigationOut:
        return InvestigationOut(
            id=record["id"],
            name=record["name"],
            description=record.get("description", ""),
            primary_wallet=record.get("primary_wallet", ""),
            network=record.get("network", "eth"),
            priority=record.get("priority", "normal"),
            risk=record.get("risk", "unknown"),
            status=record.get("status", "open"),
            transactions=len(record.get("latest_transactions") or []),
            vasp_candidates=len(record.get("latest_candidates") or []),
            evidence_count=record.get("evidence_count", 0),
            assigned_analyst=record.get("assigned_analyst", "Unassigned"),
            created_by=record.get("created_by", 0),
            latest_analysis_id=record.get("latest_analysis_id"),
            data_source=record.get("latest_data_source") or "demo",
            created_at=record.get("created_at", ""),
            updated_at=record.get("updated_at", ""),
            tags=list(record.get("tags") or []),
            is_demo=bool(getattr(self._repo, "is_demo", True)),
        )