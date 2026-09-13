"""M9 Investigator Intelligence Assistant: FastAPI endpoints.

Router-level RBAC requires ``investigation.read`` (the assistant is a
privileged investigator feature). Case ownership for case-scoped queries is
further enforced by the investigation service per request. The assistant never
runs analysis or mutates state; it is a structured, evidence-grounded query
layer.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from neo4j import Driver

from app.auth.deps import require_permission
from app.audit.service import AuditService, get_audit_service_dep
from assistant.models import AssistantRequest, AssistantResponse
from assistant.service import AssistantService
from assistant.tools import AssistantTools
from cases.api import get_investigation_service_dep
from cases.service import CaseAccessError, CaseNotFoundError
from evidence.api import get_evidence_service_dep
from graph.api import get_driver
from risk.repository import make_risk_repository
from risk.service import RiskService
from wallets.repository import make_wallet_repository
from wallets.service import WalletService

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


def get_assistant_service_dep(
    investigations=Depends(get_investigation_service_dep),
    wallet_repository=Depends(make_wallet_repository),
    evidence_service=Depends(get_evidence_service_dep),
    risk_repository=Depends(make_risk_repository),
    audit_service: AuditService = Depends(get_audit_service_dep),
    driver: Driver = Depends(get_driver),
) -> AssistantService:
    """Build the assistant on the same injected stores as the rest of the API.

    Reusing the shared repositories means a case created through
    ``/api/v1/investigations`` is immediately visible to the assistant and that
    ownership scoping, risk, evidence and the graph driver all resolve through
    the same dependency graph (hermetic in the test suite via the overrides).
    """
    tools = AssistantTools(
        investigations=investigations,
        wallets=WalletService(repository=wallet_repository),
        evidence=evidence_service,
        risk=RiskService(repository=risk_repository),
        driver=driver,
    )
    return AssistantService(tools=tools, audit=audit_service)


@router.get(
    "/quick-actions",
    response_model=list,
    summary="List quick actions the investigator assistant supports",
)
def assistant_quick_actions(
    service: AssistantService = Depends(get_assistant_service_dep),
    _current_user=Depends(require_permission("investigation.read")),
):
    return service.quick_actions()


@router.post("/query", response_model=AssistantResponse)
def assistant_query(
    payload: AssistantRequest,
    service: AssistantService = Depends(get_assistant_service_dep),
    _current_user=Depends(require_permission("investigation.read")),
):
    try:
        return service.interact(payload, _current_user)
    except CaseNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Case not found or you do not have access to it.",
        )
    except CaseAccessError:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access this case.",
        )