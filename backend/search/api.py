"""Global search API endpoint.

RBAC: every result is served under ``search.read``. Searches are audited
(action SEARCH) so investigator activity is traceable.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.audit.service import AuditService, get_audit_service_dep
from app.auth.deps import require_permission
from cases.repository import InvestigationRepository, make_investigation_repository
from evidence.api import get_evidence_service_dep
from search.models import GlobalSearchResponse, SearchEntityType
from search.service import SearchService
from wallets.repository import WalletRepository, make_wallet_repository

router = APIRouter(prefix="/api/v1/search", tags=["search"])


def get_search_service_dep(
    investigation_repository: InvestigationRepository = Depends(
        make_investigation_repository
    ),
    wallet_repository: WalletRepository = Depends(make_wallet_repository),
    evidence_service=Depends(get_evidence_service_dep),
) -> SearchService:
    return SearchService(
        investigation_repository=investigation_repository,
        wallet_repository=wallet_repository,
        evidence_service=evidence_service,
    )


@router.get(
    "",
    response_model=GlobalSearchResponse,
    responses={
        200: {"description": "Global search completed"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def global_search(
    q: str = Query(..., min_length=1, max_length=128, description="Search term"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    entity_type: SearchEntityType | None = Query(
        None, description="Restrict to one entity type"
    ),
    audit_service: AuditService = Depends(get_audit_service_dep),
    service: SearchService = Depends(get_search_service_dep),
    current_user=Depends(require_permission("search.read")),
):
    """Search persisted investigations, wallets, transactions, evidence,
    analyses, curated VASPs, and reports."""
    results = service.search(
        q, limit=limit, entity_types=[entity_type] if entity_type else None
    )
    audit_service.record_event(
        user=current_user.username,
        action="SEARCH",
        resource="global",
        resource_id="",
        result=f"hits:{len(results)}",
    )
    source = "postgres" if any(r.source == "postgres" for r in results) else "memory"
    return GlobalSearchResponse(
        query=q,
        results=results,
        total=len(results),
        source=source,
    )