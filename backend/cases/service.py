"""Investigation service: business rules, ownership scoping, and the
apply-analysis flow that attaches live analysis output to a persisted case."""

from __future__ import annotations

from typing import List, Optional

from cases.models import (
    InvestigationContext,
    InvestigationCreate,
    InvestigationListResponse,
    InvestigationNoteCreate,
    InvestigationNoteListResponse,
    InvestigationNoteOut,
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

# Analyst and reviewer may open any case in read-only, analyst builds
# evidence on them, reviewer audits them. Writes remain admin/senior only.
_READ_ALL_ROLES = _ADMIN_ROLES | {"analyst", "reviewer"}


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
        if user.role in _READ_ALL_ROLES:
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
        if owner_only and user.role not in _READ_ALL_ROLES:
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

    def record_for(self, case_id: str, user) -> dict:
        """Return the raw persisted case record (ownership-scoped).

        Unlike the aggregated ``InvestigationOut``, the raw record also
        carries the stored ``latest_candidates`` / ``latest_transactions``
        payloads, which the assistant needs when it grounds answers in the
        most recent persisted analysis output.
        """
        return self._require_case(case_id, user)

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

    def notes(self, case_id: str, user) -> InvestigationNoteListResponse:
        """List persisted analyst notes for a case (ownership-scoped read)."""
        self._require_case(case_id, user)
        notes = self._repo.list_notes(case_id)
        return InvestigationNoteListResponse(
            notes=[self._to_note_out(n) for n in notes],
            total=len(notes),
            case_id=case_id,
        )

    def add_note(
        self, case_id: str, payload: InvestigationNoteCreate, user
    ) -> InvestigationNoteOut:
        """Persist an analyst note on a case (ownership-scoped write)."""
        case = self._require_case(case_id, user)
        if not self._can_write(case, user):
            raise CaseAccessError(case_id)
        record = self._repo.add_note(
            case_id, {"author": payload.author, "body": payload.body}
        )
        return self._to_note_out(record)

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

    def attach_report(self, case_id: str, report_id: str, user) -> InvestigationOut:
        """Record a generated report id on the case (bounded history)."""
        case = self._require_case(case_id, user)
        if not self._can_write(case, user):
            raise CaseAccessError(case_id)
        history = list(case.get("latest_report_ids") or [])
        if report_id not in history:
            history.append(report_id)
        record = self._repo.update(case_id, {"latest_report_ids": history[-20:]})
        return self._to_out(record)

    def context(self, case_id: str, user) -> InvestigationContext:
        """Aggregate the persisted investigation context for an investigator.

        Returns the case, its wallet summary, the latest analysis, linked
        evidence, the analytical risk, and generated report ids. Every field
        is real persisted data — nothing is ever fabricated for the context.
        """
        case = self._require_case(case_id, user)
        out = self._to_out(case)

        summary = self._wallet_service.summarize(
            case.get("primary_wallet", ""), case.get("network", "eth")
        )

        latest_analysis = None
        if case.get("latest_analysis_id"):
            latest_analysis = {
                "analysis_id": case.get("latest_analysis_id"),
                "data_source": case.get("latest_data_source") or "demo",
                "candidate_count": len(case.get("latest_candidates") or []),
                "transaction_count": len(case.get("latest_transactions") or []),
                # Persisted candidate payload so report previews and the
                # assistant can reuse the stored analysis instead of re-running
                # the full pipeline (which would burn a rate-limit analyze
                # bucket on every page open).
                "candidates": case.get("latest_candidates") or [],
            }

        evidence = self._evidence.get_evidence_for_investigation(case_id)

        risk = self._risk_service.get_for_investigation(case_id)
        if risk is None and (case.get("latest_candidates") or case.get("latest_transactions")):
            risk = self._risk_service.evaluate(
                address=case.get("primary_wallet", ""),
                chain=case.get("network", "eth"),
                candidates=case.get("latest_candidates") or [],
                transfers=case.get("latest_transactions") or [],
                evidence_count=case.get("evidence_count", 0),
                investigation_id=case_id,
            )

        return InvestigationContext(
            case=out,
            wallet_summary=summary.model_dump() if summary else None,
            latest_analysis=latest_analysis,
            evidence=evidence,
            risk=risk,
            reports=list(case.get("latest_report_ids") or []),
            scope="admin" if user.role in _ADMIN_ROLES else ("read_all" if user.role in {"analyst", "reviewer"} else "owned"),
        )

    def _to_out(self, record: dict) -> InvestigationOut:
        # "transactions" = the wallet-level set persisted by the analysis
        # pipeline (unique rows in the wallet store). "latest_transactions"
        # is the most-recent ingestion batch, so the reported counts can
        # legitimately differ on-chain because repeated internal transfers
        # are de-duplicated in the wallet store.
        persisted_transactions = 0
        summary = self._wallet_service.summarize(
            record.get("primary_wallet", ""), record.get("network", "eth")
        )
        if summary is not None:
            persisted_transactions = summary.transaction_count
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
            persisted_transactions=persisted_transactions,
            vasp_candidates=len(record.get("latest_candidates") or []),
            evidence_count=record.get("evidence_count", 0),
            assigned_analyst=record.get("assigned_analyst", "Unassigned"),
            created_by=record.get("created_by", 0),
            latest_analysis_id=record.get("latest_analysis_id"),
            latest_report_ids=list(record.get("latest_report_ids") or []),
            data_source=record.get("latest_data_source") or "demo",
            created_at=record.get("created_at", ""),
            updated_at=record.get("updated_at", ""),
            tags=list(record.get("tags") or []),
            is_demo=bool(getattr(self._repo, "is_demo", True)),
        )

    def _to_note_out(self, record: dict) -> InvestigationNoteOut:
        return InvestigationNoteOut(
            id=record["id"],
            case_id=record["case_id"],
            author=record["author"],
            body=record["body"],
            created_at=record["created_at"],
        )