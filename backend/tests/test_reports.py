"""Tests for the server-side PDF report surface."""

import pytest

from reports import models as report_models
from reports.service import build_pdf_bytes


def _metadata(**overrides):
    data = {
        "case_id": None,
        "case_name": "Test case",
        "investigator": "Investigator A",
        "generated_at": "2026-01-01T00:00:00Z",
        "classification": "UNCLASSIFIED",
        "network": "eth",
        "primary_wallet": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    }
    data.update(overrides)
    return report_models.ReportMetadata(**data)


class TestReportContent:
    def test_section_titles_cover_supported_keys(self):
        assert set(report_models._SECTION_TITLES) == set(
            report_models.REPORT_SECTIONS
        )

    def test_section_content_marks_unavailable(self):
        text = report_models.build_section_content("wallet_overview", {"case": {}, "metadata": {}})
        assert "UNAVAILABLE" in text

    def test_section_content_uses_case_data(self):
        context = {
            "metadata": {},
            "case": {
                "primary_wallet": "0xaaa",
                "network": "eth",
                "status": "open",
                "name": "Alpha",
                "latest_data_source": "live",
                "evidence_count": 4,
            },
        }
        text = report_models.build_section_content("executive_summary", context)
        assert "Alpha" in text
        assert "live" in text

    def test_unknown_section_marked_unrecognized(self):
        text = report_models.build_section_content("nonsense_section", {})
        assert "not recognized" in text


class TestPdfBuild:
    def test_build_pdf_returns_pdf_bytes(self):
        pdf_bytes, rendered = build_pdf_bytes(
            _metadata(), {"metadata": _metadata().model_dump(), "selected_sections": []}
        )
        assert pdf_bytes.startswith(b"%PDF")
        assert rendered > 0

    def test_rendered_section_count(self):
        pdf_bytes, rendered = build_pdf_bytes(
            _metadata(),
            {
                "metadata": _metadata().model_dump(),
                "selected_sections": ["executive_summary", "conclusion"],
            },
        )
        assert rendered == 2


class TestReportsAPI:
    def test_sections_endpoint(self, app_client):
        resp = app_client.get("/api/v1/reports/sections")
        assert resp.status_code == 200
        assert "executive_summary" in resp.json()["sections"]

    def test_export_pdf_streams_bytes(self, app_client):
        resp = app_client.post(
            "/api/v1/reports/export",
            json={
                "metadata": _metadata(case_id=None).model_dump(),
                "sections": ["executive_summary", "wallet_overview"],
            },
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/pdf")
        assert resp.content.startswith(b"%PDF")
        assert resp.headers.get("x-cryptotrace-report-id", "").startswith("rpt-")

    def test_export_with_case_context(self, app_client):
        case = app_client.post(
            "/api/v1/investigations",
            json={
                "name": "report case",
                "primary_wallet": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            },
        ).json()
        resp = app_client.post(
            "/api/v1/reports/export",
            json={
                "metadata": _metadata(case_id=case["id"]).model_dump(),
                "sections": ["investigation_details"],
            },
        )
        assert resp.status_code == 200
        assert resp.content.startswith(b"%PDF")

    def test_export_context_uses_persisted_analysis_payloads(self, app_client):
        """Regression: _resolve_context must read the RAW case record
        (latest_transactions / latest_candidates), not the aggregated
        InvestigationOut which strips those payloads — otherwise populated
        cases render UNAVAILABLE sections."""
        from cases.service import InvestigationService
        from evidence.repository import EvidenceRepository
        from risk.repository import MemoryRiskRepository
        from wallets.repository import MemoryWalletRepository

        case = app_client.post(
            "/api/v1/investigations",
            json={
                "name": "context case",
                "primary_wallet": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            },
        ).json()
        app_client._test_cases_repo.update(
            case["id"],
            {
                "latest_data_source": "live",
                "latest_transactions": [
                    {
                        "block_timestamp": "2026-09-01T00:00:00Z",
                        "from_address": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                        "to_address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                        "value": "1.5",
                        "token_symbol": "ETH",
                    }
                ],
                "latest_candidates": [
                    {
                        "score": 87,
                        "confidence": "HIGH",
                        "vasp_name": "SynthExchange_A",
                    }
                ],
            },
        )

        service = InvestigationService(
            repository=app_client._test_cases_repo,
            evidence_service=EvidenceRepository(),
            wallet_repository=MemoryWalletRepository(),
            risk_repository=MemoryRiskRepository(),
        )
        from reports.api import _resolve_context
        from reports.models import ReportMetadata

        context = _resolve_context(
            ReportMetadata(
                case_id=case["id"],
                case_name="context case",
                primary_wallet="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                network="eth",
            ),
            service,
        )
        # The raw record (not InvestigationOut) must carry the payloads.
        assert len(context["case"]["latest_transactions"]) == 1
        assert len(context["case"]["latest_candidates"]) == 1

        overview = report_models.build_section_content("wallet_overview", context)
        assert "Transactions persisted: 1" in overview
        assert "VASP candidates ranked: 1" in overview

        tx_analysis = report_models.build_section_content("transaction_analysis", context)
        assert "1.5" in tx_analysis
        assert "No persisted transaction set" not in tx_analysis

        candidates = report_models.build_section_content("vasp_candidates", context)
        assert "SynthExchange_A" in candidates
        assert "No VASP attribution candidates" not in candidates

        appendix = report_models.build_section_content("appendix", context)
        assert "live" in appendix
        assert "Alchemy" in appendix