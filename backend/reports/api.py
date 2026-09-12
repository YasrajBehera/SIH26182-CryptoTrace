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


def _resolve_context(metadata: report_models.ReportMetadata, service) -> dict:
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
            case = service.get(metadata.case_id, service_user())
        except Exception:
            case = None
        if case:
            context["case"] = case.model_dump()
            assessment = service.risk_for(metadata.case_id, service_user())
            if assessment:
                context["risk_disclaimer"] = assessment.disclaimer
    return context


def service_user():
    """Reports pull persisted data the way any reader would; the owning
    investigation service enforces ownership scoping when a case id is set."""
    from app.auth.demo import DEMO_USERS
    from app.auth.models import User

    admin_spec = next(u for u in DEMO_USERS if u["username"] == "admin")
    return User(
        id=int(admin_spec.get("id") or 1),
        username=admin_spec["username"],
        role=admin_spec["role"],
        title=admin_spec.get("title", ""),
    )


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
    from cases.api import get_investigation_service_dep

    investigation_service = get_investigation_service_dep()

    metadata = payload.metadata
    generated_at = metadata.generated_at or datetime.now(timezone.utc).isoformat()
    metadata.generated_at = generated_at

    context = _resolve_context(metadata, investigation_service)
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