"""Server-side PDF report export contract and content assembly.

The report is generated on the server from persisted investigation data.
Sections that have no persisted data are explicitly marked UNAVAILABLE so the
artefact never implies information the system did not actually hold.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field

REPORT_SECTIONS = [
    "executive_summary",
    "investigation_details",
    "wallet_overview",
    "transaction_analysis",
    "fund_flow",
    "graph_analysis",
    "vasp_candidates",
    "evidence",
    "risk_assessment",
    "analyst_notes",
    "timeline",
    "conclusion",
    "appendix",
]

_SECTION_TITLES = {
    "executive_summary": "Executive Summary",
    "investigation_details": "Investigation Details",
    "wallet_overview": "Wallet Overview",
    "transaction_analysis": "Transaction Analysis",
    "fund_flow": "Fund Flow",
    "graph_analysis": "Graph Analysis",
    "vasp_candidates": "VASP Candidates",
    "evidence": "Evidence Record",
    "risk_assessment": "Risk Assessment",
    "analyst_notes": "Analyst Notes",
    "timeline": "Timeline",
    "conclusion": "Conclusion",
    "appendix": "Appendix",
}


class ReportMetadata(BaseModel):
    case_id: Optional[str] = None
    case_name: str = "Untitled investigation"
    investigator: str = ""
    generated_at: Optional[str] = None
    classification: str = "UNCLASSIFIED"
    network: str = "eth"
    primary_wallet: Optional[str] = None


class ReportExportRequest(BaseModel):
    metadata: ReportMetadata
    sections: List[str] = Field(default_factory=list)


class ReportExportResult(BaseModel):
    report_id: str
    status: str = "ready"
    format: str = "pdf"
    content_type: str = "application/pdf"
    byte_count: int = 0
    sections_rendered: int = 0
    generated_at: str = ""
    message: str = ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_section_content(key: str, context: dict) -> str:
    """Render one approved section. Explicit sections kept in-sync with the
    frontend ReportSectionKey union."""
    case = context.get("case") or {}
    if key == "executive_summary":
        name = case.get("name") or context.get("metadata", {}).get("case_name", "Untitled investigation")
        return (
            f"This report summarizes the blockchain investigation of "
            f"{case.get('primary_wallet') or context.get('metadata', {}).get('primary_wallet') or 'the subject wallet'} "
            f"on the {case.get('network') or context.get('metadata', {}).get('network', 'eth')} network.\n\n"
            f"Investigation reference: {name}.\n\n"
            f"Data source reported by the pipeline: "
            f"{case.get('latest_data_source', 'UNAVAILABLE')}.\n"
            "Analytical risk scores are heuristic rankings, not determinations "
            "of criminality or ownership."
        )
    if key == "investigation_details":
        return (
            f"Case ID: {case.get('id') or 'UNAVAILABLE'}\n"
            f"Case name: {case.get('name') or 'UNAVAILABLE'}\n"
            f"Primary wallet: {case.get('primary_wallet') or 'UNAVAILABLE'}\n"
            f"Network: {case.get('network') or 'UNAVAILABLE'}\n"
            f"Status: {case.get('status') or 'UNAVAILABLE'}\n"
            f"Priority: {case.get('priority') or 'UNAVAILABLE'}\n"
            f"Assigned analyst: {case.get('assigned_analyst') or 'UNAVAILABLE'}\n"
            f"Classification: "
            f"{context.get('metadata', {}).get('classification', 'UNCLASSIFIED')}"
        )
    if key == "wallet_overview":
        txns = case.get("transactions")
        if txns is None:
            txns = len(case.get("latest_transactions") or [])
        candidates_n = case.get("vasp_candidates")
        if candidates_n is None:
            candidates_n = len(case.get("latest_candidates") or [])
        return (
            f"Primary wallet: {case.get('primary_wallet') or 'UNAVAILABLE'}\n"
            f"Latest analysis: {case.get('latest_analysis_id') or 'UNAVAILABLE'}\n"
            f"Transactions persisted: {txns if txns is not None else 'UNAVAILABLE'}\n"
            f"VASP candidates ranked: {candidates_n if candidates_n is not None else 'UNAVAILABLE'}\n"
            f"Risk label: {case.get('risk') or 'UNAVAILABLE'}"
        )
    if key == "transaction_analysis":
        txs = case.get("latest_transactions") or []
        if not txs:
            return "No persisted transaction set available for this case."
        lines = [
            "Analyzed transactions (up to 25 shown):",
            "-" * 40,
        ]
        for tx in txs[:25]:
            lines.append(
                f"{tx.get('block_timestamp', '?')} "
                f"{tx.get('from_address')} -> {tx.get('to_address')} "
                f"{tx.get('value')} {tx.get('token_symbol') or 'ETH'}"
            )
        return "\n".join(lines)
    if key == "fund_flow":
        return (
            "Funds flowing between the subject wallet and its direct "
            "counterparties are captured in the evidence `graph_path` records. "
            "Swap-level fund flow across multiple hops is computed in the graph "
            "module (Neo4j) and may be UNAVAILABLE when the graph store is offline."
        )
    if key == "graph_analysis":
        return (
            "Graph analytics (BFS/DFS/flow/clusters) are served by the Neo4j "
            "module. Graph data source status: "
            f"{context.get('graph_status', 'UNAVAILABLE')}."
        )
    if key == "vasp_candidates":
        candidates = case.get("latest_candidates") or []
        if not candidates:
            return "No VASP attribution candidates available for this case."
        lines = ["Ranked VASP attribution candidates:", "-" * 40]
        for c in candidates:
            lines.append(
                f"{c.get('score', 0):>5.1f}/100 {c.get('confidence', '?')}  {c.get('vasp_name')}"
            )
        return "\n".join(lines)
    if key == "evidence":
        return (
            f"Evidence count linked to case: "
            f"{case.get('evidence_count', 0)}.\n"
            "Each evidence record carries provenance (created_by, method, "
            "created_at) accessible via GET /api/v1/evidence/investigation/{id}."
        )
    if key == "risk_assessment":
        return (
            f"Analytical risk: {case.get('risk') or 'UNAVAILABLE'}.\n"
            "Risk scores are analytical heuristics only; they are NOT "
            "determinations of criminality, illegality, or ownership.\n"
            "Disclaimer: " + context.get("risk_disclaimer", "")
        )
    if key == "analyst_notes":
        return (
            "Analyst notes are maintained in the case workspace. Notes entered "
            "against an investigation are exported verbatim when the case is "
            "persisted; otherwise this section is UNAVAILABLE."
        )
    if key == "timeline":
        return (
            f"Created: {case.get('created_at') or 'UNAVAILABLE'}\n"
            f"Updated: {case.get('updated_at') or 'UNAVAILABLE'}\n"
            f"Report generated: "
            f"{context.get('metadata', {}).get('generated_at') or 'UNAVAILABLE'}"
        )
    if key == "conclusion":
        return (
            "This investigation report synthesizes on-chain activity, "
            "attribution scoring, and analytical risk into a single artefact "
            "for review. All scores are heuristic; final classification is the "
            "responsibility of the investigating analyst."
        )
    if key == "appendix":
        return (
            "Appendix - Data provenance.\n"
            "Blockchain provider available to the pipeline: Alchemy "
            "(getAssetTransfers normalization; reachability depends on the "
            "deployment environment).\n"
            "Case data source: " + (case.get('latest_data_source') or 'UNAVAILABLE') + ".\n"
            "Report generated server-side by CryptoTrace (SIH26182)."
        )
    return f"Section {key} is not recognized; content unavailable."


def new_report_id() -> str:
    return f"rpt-{uuid.uuid4().hex[:12]}"