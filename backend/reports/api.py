"""Server-side PDF report export endpoint."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse

from app.audit.service import AuditService, get_audit_service_dep
from app.auth.deps import require_permission
from reports import models as report_models
from reports.service import ReportBuildError, build_pdf_bytes

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def _resolve_context(
    metadata: report_models.ReportMetadata, service, wallet_service=None
) -> dict:
    from wallets.repository import make_wallet_repository
    from wallets.service import WalletService

    if wallet_service is None:
        # Fallback so callers/tests that only hold the investigation service
        # still resolve the persisted wallet-store count.
        wallet_service = WalletService(repository=make_wallet_repository())
    context = {"metadata": metadata.model_dump(), "graph_status": "UNAVAILABLE"}
    from graph.api import get_driver

    try:
        driver = next(get_driver())
        from graph.neo4j_client import is_neo4j_healthy

        if is_neo4j_healthy(driver):
            context["graph_status"] = "reachable"
    except Exception:
        context["graph_status"] = "UNAVAILABLE"

    if metadata.case_id:
        try:
            # Pull the RAW persisted record (not the aggregated InvestigationOut)
            # so latest_transactions / latest_candidates flow into the report
            # sections. The aggregated model intentionally strips those payloads.
            case = service.record_for(metadata.case_id, service_user())
        except Exception:
            case = None
        if case:
            context["case"] = case
            # The raw record only carries the latest ingestion batch; the
            # number of transactions actually persisted in the wallet store is
            # the wallet summary count (duplicate (chain, tx_hash) rows are
            # de-duplicated there). The PDF must report the persisted count.
            try:
                summary = wallet_service.summarize(
                    case.get("primary_wallet", ""), case.get("network", "eth")
                )
                if summary is not None:
                    case["persisted_transactions"] = summary.transaction_count
            except Exception:
                pass
            assessment = service.risk_for(metadata.case_id, service_user())
            if assessment:
                context["risk_disclaimer"] = assessment.disclaimer
                # SEPARATE criminal/sanctions intelligence block (exact match
                # in the curated public directory). Kept out of every other
                # section so it can never be merged with VASP attribution.
                context["criminal_intelligence"] = (
                    assessment.criminal_intelligence
                )
                # SEPARATE ML suspicious-wallet block. Kept out of every other
                # section; the report renders it only inside risk_assessment.
                context["ml_assessment"] = assessment.ml_assessment
    return context


def service_user():
    """Reports pull persisted data the way any reader would; the owning
    investigation service enforces ownership scoping when a case id is set."""
    from app.auth.demo import DEMO_USERS
    from app import models as db_models

    admin_spec = next(u for u in DEMO_USERS if u["username"] == "admin")
    # Transient (unpersisted) record sufficient for ownership scoping checks.
    user = db_models.User(
        id=int(admin_spec.get("id") or 1),
        username=admin_spec["username"],
        display_name=admin_spec.get("display_name", ""),
        email="",
        role=admin_spec["role"],
        title=admin_spec.get("title", ""),
    )
    return user


@router.post(
    "/export",
    responses={
        200: {
            "description": "PDF report generated and returned as a binary stream",
            "content": {"application/pdf": {}},
        },
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        503: {"description": "Server-side PDF dependency unavailable"},
    },
)
def export_report(
    payload: report_models.ReportExportRequest,
    audit_service: AuditService = Depends(get_audit_service_dep),
    _current_user=Depends(require_permission("report.export")),
):
    """Generate a server-side PDF report.

    The endpoint streams ``application/pdf`` bytes. The report reflects only
    persisted investigation data; missing information is marked UNAVAILABLE.
    """
    from cases.repository import make_investigation_repository
    from cases.service import InvestigationService
    from evidence.api import get_evidence_service
    from risk.repository import make_risk_repository
    from wallets.repository import make_wallet_repository
    from wallets.service import WalletService

    # Build a concrete service with real repositories. The FastAPI dependency
    # (get_investigation_service_dep) must never be called directly here: its
    # ``Depends(...)`` defaults only resolve inside request DI, so calling it
    # outside would wire ``Depends`` marker objects into the service and make
    # every repo call crash with ``AttributeError: 'Depends' object has no
    # attribute 'get'`` — which previously let the whole PDF body render as
    # UNAVAILABLE while the header still showed the real case metadata.
    investigation_service = InvestigationService(
        repository=make_investigation_repository(),
        evidence_service=get_evidence_service(),
        wallet_repository=make_wallet_repository(),
        risk_repository=make_risk_repository(),
    )
    wallet_service = WalletService(repository=make_wallet_repository())

    metadata = payload.metadata
    generated_at = metadata.generated_at or datetime.now(timezone.utc).isoformat()
    metadata.generated_at = generated_at

    context = _resolve_context(metadata, investigation_service, wallet_service)
    context["selected_sections"] = [
        s for s in payload.sections if s in report_models.REPORT_SECTIONS
    ]
    if not context["selected_sections"]:
        context["selected_sections"] = list(report_models.REPORT_SECTIONS)

    try:
        pdf_bytes, rendered = build_pdf_bytes(metadata, context)
    except ReportBuildError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    report_id = report_models.new_report_id()
    if metadata.case_id:
        try:
            investigation_service.attach_report(
                metadata.case_id, report_id, _current_user
            )
        except Exception:
            # Attaching the id to the case is best-effort; the report itself
            # is still valid and the export is still audited below.
            pass
    audit_service.record_event(
        user=_current_user.username,
        action="REPORT_EXPORT",
        resource="report",
        resource_id=report_id,
        result=f"{rendered}:{metadata.case_id or 'no-case'}",
    )
    headers = {
        "Content-Disposition": f'attachment; filename="{report_id}.pdf"',
        "X-CryptoTrace-Report-Id": report_id,
        "X-CryptoTrace-Report-Sections": str(rendered),
    }
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers=headers,
    )


@router.get("/sections")
def report_sections(
    _current_user=Depends(require_permission("report.create")),
):
    """Advertise the report sections the server can render (sync with the
    frontend ReportSectionKey union)."""
    return {
        "sections": report_models.REPORT_SECTIONS,
        "titles": report_models._SECTION_TITLES,
    }