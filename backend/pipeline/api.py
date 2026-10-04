"""Investigation HTTP surface.

The endpoint is a thin adapter over :class:`~pipeline.service.InvestigationPipeline`:

* it passes the caller-selected ``mode`` straight through, so synthetic data can
  only ever appear when the caller asked for it (``demo``) or when the documented
  ``auto`` mode reports the live failure in ``status`` / ``live_status`` /
  ``limitations`` and replaces the rows with synthetic ones;
* every typed pipeline failure is mapped to an accurate HTTP status. A live
  investigation that cannot be completed is never reported as a success.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.audit.service import AuditService, get_audit_service_dep
from app.auth.deps import CurrentUser, require_permission
from blockchain.chains import CHAIN_ALIASES, resolve_chain
from blockchain.errors import BlockchainError, UnsupportedChainError
from cases.api import get_investigation_service
from cases.service import CaseConflictError, CaseNotFoundError
from pipeline.models import InvestigationRequest, InvestigationResult
from pipeline.service import MODE_AUTO, MODE_DEMO, MODE_LIVE, InvestigationPipeline

router = APIRouter(prefix="/api/v1/investigations", tags=["investigations"])

_pipeline = InvestigationPipeline()


def _fail(exc: Exception, *, status: str, status_code: int) -> HTTPException:
    """Build an error response that never looks like a successful analysis."""
    return HTTPException(
        status_code=status_code,
        detail={
            "status": status,
            "data_source": "unavailable",
            "message": str(exc),
        },
    )


def _handle_pipeline_error(exc: Exception) -> HTTPException:
    """Map a typed pipeline failure onto its accurate HTTP status.

    Every provider error declares both a machine-readable ``status`` and the
    ``http_status`` it should surface as, so the mapping stays in one place and
    cannot drift from the error taxonomy.
    """
    status = getattr(exc, "status", "LIVE_DATA_UNAVAILABLE")
    status_code = getattr(exc, "http_status", 503)
    return _fail(exc, status=status, status_code=int(status_code))


@router.get(
    "/chains",
    responses={200: {"description": "Supported investigation chains and aliases"}},
)
def list_chains(_current_user: CurrentUser = Depends(require_permission("wallet.analyze"))):
    """Chains this deployment can investigate, plus the aliases accepted by ``chain``."""
    from blockchain.registry import provider_status

    return {"chains": provider_status(), "aliases": dict(sorted(CHAIN_ALIASES.items()))}


@router.post(
    "/{address}/analyze",
    response_model=InvestigationResult,
    responses={
        200: {"description": "Investigation complete"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Investigation (case) not found"},
        409: {"description": "Analysis ran against a different wallet than the case"},
        422: {"description": "Unsupported chain or malformed address"},
        429: {"description": "Upstream provider rate limit reached"},
        503: {"description": "Live chain data unavailable (strict mode)"},
        504: {"description": "Upstream provider timed out"},
    },
)
def analyze_investigation(
    address: str = Path(...),
    chain: str = Query("eth", description="Canonical chain id or a known alias"),
    limit: int | None = Query(None, ge=1, le=10000),
    mode: str = Query(
        MODE_AUTO,
        pattern="^(live|demo|auto)$",
        description=(
            "live: real chain data only; a provider failure is an HTTP 503 and no "
            "synthetic data is substituted. demo: synthetic data only, never a "
            "live fetch. auto (default): real data when the provider has any, "
            "otherwise clearly-labelled synthetic demo data with the live status "
            "reported in `status`, `live_status` and `limitations`."
        ),
    ),
    case_id: Optional[str] = Query(
        None, description="Optional persisted investigation to attach results to"
    ),
    investigation_service=Depends(get_investigation_service),
    audit_service: AuditService = Depends(get_audit_service_dep),
    _current_user: CurrentUser = Depends(require_permission("wallet.analyze")),
):
    """Full pipeline: real (or explicitly requested synthetic) transfers -> graph ->
    attribution -> evidence.

    If ``case_id`` is supplied the analysis is ALSO bound to the persisted
    investigation (evidence, wallet summary, risk, candidates)."""
    # Resolve the chain here so an unknown chain is a clean 422 and the pipeline
    # only ever sees canonical ids.
    try:
        resolve_chain(chain)
    except UnsupportedChainError as exc:
        raise _handle_pipeline_error(exc) from exc

    request = InvestigationRequest(address=address, chain=chain, limit=limit)
    try:
        result = _pipeline.run(request, mode=mode)
    except BlockchainError as exc:
        raise _handle_pipeline_error(exc) from exc
    except ValueError as exc:
        # Bad mode/limit combination: a caller error, not a provider failure.
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    audit_service.record_event(
        user=_current_user.username,
        action="ANALYZE",
        resource="investigation",
        resource_id=address,
        result=f"{result.data_source}:{result.status}",
    )

    if case_id:
        try:
            investigation_service.apply_analysis(
                case_id=case_id,
                address=result.address,
                analysis_id=result.analysis_id,
                data_source=result.data_source,
                candidates=[c.model_dump() for c in result.candidates],
                transactions=result.transactions,
                user=_current_user,
            )
        except CaseNotFoundError:
            raise HTTPException(status_code=404, detail="Investigation not found")
        except CaseConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        result.case_id = case_id

    return result


__all__ = ["router", "MODE_LIVE", "MODE_DEMO", "MODE_AUTO"]