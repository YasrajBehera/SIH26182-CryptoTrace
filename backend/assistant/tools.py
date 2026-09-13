"""Controlled, read-only tool layer for the M9 assistant.

Every method here only READS persisted application data (cases, wallets,
transactions, evidence, risk, reports). No tool runs a new analysis, mutates
state, generates a report, or submits anything to an external system. Failed
data sources resolve to ``None`` so the service can answer honestly with
"unavailable" rather than inventing values.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

from attribution.service import AttributionService
from cases.models import InvestigationContext
from cases.service import InvestigationService
from evidence.service import EvidenceService
from risk.service import RiskAssessment, RiskService
from wallets.service import WalletService

_WALLET_RE = re.compile(r"0x[a-fA-F0-9]{40}")


def extract_addresses(text: str) -> List[str]:
    """Pull up to two 0x addresses out of free-form query text."""
    return _WALLET_RE.findall(text)[:2]


def iso_utc(ts) -> Optional[str]:
    """Render an integer unix timestamp as ISO-8601 UTC (never invented)."""
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def visible_ids(rows: List[dict], key: str, limit: int = 200) -> List[str]:
    seen: List[str] = []
    for row in rows:
        value = row.get(key)
        if value:
            seen.append(str(value))
    return seen[:limit]


class AssistantToolError(Exception):
    """Base for tool failures that must surface as honest "unavailable"."""


class AssistantTools:
    """Dependency facade that wires the assistant to the read-only services."""

    def __init__(
        self,
        investigations: Optional[InvestigationService] = None,
        wallets: Optional[WalletService] = None,
        evidence: Optional[EvidenceService] = None,
        risk: Optional[RiskService] = None,
        attribution: Optional[AttributionService] = None,
        driver=None,
    ) -> None:
        self.investigations = investigations or InvestigationService()
        self.wallets = wallets or WalletService()
        self.evidence = evidence or EvidenceService()
        self.risk = risk or RiskService()
        self.attribution = attribution or AttributionService()
        self._driver = driver

    # ---- Case scope --------------------------------------------------------

    def get_case(self, case_id: str, user) -> InvestigationContext:
        """Aggregate the persisted investigation context.

        Ownership is enforced inside ``InvestigationService.context`` (raises
        ``CaseNotFoundError`` for non-owners / missing cases).
        """
        return self.investigations.context(case_id, user)

    def get_case_record(self, case_id: str, user) -> dict:
        """Raw, ownership-scoped persisted case record (with analysis payloads)."""
        return self.investigations.record_for(case_id, user)

    def get_case_candidates(self, record: dict) -> List[dict]:
        return list(record.get("latest_candidates") or [])

    def get_case_transactions(self, ctx: InvestigationContext) -> List[dict]:
        case = ctx.case
        stored = self.wallets.repository.list_transactions(
            address=case.primary_wallet, chain=case.network, limit=500
        )
        if stored:
            return stored
        return list(getattr(ctx.case, "latest_transactions", None) or [])

    # ---- Wallet scope ------------------------------------------------------

    def get_wallet(self, address: str, chain: str, user) -> Optional[dict]:
        """Persisted wallet summary (risk/activity recorded by past analyses)."""
        summary = self.wallets.summarize(address, chain)
        return summary.model_dump() if summary else None

    def get_transactions(self, address: str, chain: str, user, limit: int = 500):
        return self.wallets.repository.list_transactions(
            address=address, chain=chain, limit=limit
        )

    def get_evidence(self, address: str, chain: str, user):
        address = address.lower()
        records = self.evidence.repository.get_by_address(address, chain)
        return records or self.evidence.repository.get_by_address(address, "eth")

    def get_risk(self, address: str, chain: str, user) -> Optional[RiskAssessment]:
        return self.risk.get_for_wallet(address, chain)

    def get_evidence_for_investigation(self, case_id: str, user):
        return self.evidence.get_evidence_for_investigation(case_id)

    # ---- Graph / tracing (server-backed, graceful when offline) ------------

    def get_graph(self, wallet_address: str, chain: str, user) -> Optional[dict]:
        """BFS neighbors + edges for the wallet, or None when Neo4j is down."""
        wallet_id = f"{chain}:{wallet_address.lower()}"
        driver, owned = self._resolve_driver()
        if driver is None:
            return None
        try:
            from graph import service as graph_service

            nodes = graph_service.bfs(driver, wallet_id, max_depth=2, max_nodes=100)
            edges = graph_service.bfs_edges(
                driver, wallet_id, max_depth=2, max_edges=200
            )
            return {"nodes": nodes, "edges": edges}
        except Exception:
            return None
        finally:
            if owned:
                self._close_driver(driver)

    def get_fund_flow(self, source_addr: str, target_addr: str, chain: str) -> dict:
        """Shortest hop path between two wallets.

        Prefers a live Neo4j calculation; falls back to a bounded hop walk over
        the stored transaction set. Either way the path is real stored data.
        """
        source_wid = f"{chain}:{source_addr.lower()}"
        target_wid = f"{chain}:{target_addr.lower()}"
        driver, owned = self._resolve_driver()
        if driver is not None:
            try:
                from graph import service as graph_service

                return graph_service.shortest_path(
                    driver,
                    source=source_wid,
                    target=target_wid,
                    weight="hops",
                )
            except Exception:
                pass
            finally:
                if owned:
                    self._close_driver(driver)
        return self._path_from_stored_transactions(
            chain, source_addr.lower(), target_addr.lower()
        )

    def _path_from_stored_transactions(
        self, chain: str, source_addr: str, target_addr: str, max_depth: int = 4
    ) -> dict:
        frontier = [(source_addr, [source_addr])]
        visited = {source_addr}
        for _ in range(max_depth):
            next_frontier: List[tuple] = []
            for address, path in frontier:
                rows = self.wallets.repository.list_transactions(
                    address=address, chain=chain, limit=200
                )
                for row in rows:
                    counterparty = (
                        row.get("to_address", "").lower()
                        if (row.get("from_address") or "").lower() == address
                        else row.get("from_address", "").lower()
                    )
                    if not counterparty or counterparty in visited:
                        continue
                    visited.add(counterparty)
                    next_frontier.append((counterparty, path + [counterparty]))
                    if counterparty == target_addr:
                        return {
                            "source": f"{chain}:{source_addr}",
                            "target": f"{chain}:{target_addr}",
                            "weight": "hops",
                            "found": True,
                            "total_cost": len(path),
                            "nodes": [{"wallet_id": f"{chain}:{a}"} for a in path + [counterparty]],
                        }
            frontier = next_frontier
        return {
            "source": f"{chain}:{source_addr}",
            "target": f"{chain}:{target_addr}",
            "weight": "hops",
            "found": False,
            "total_cost": None,
            "nodes": [],
        }

    def _resolve_driver(self):
        """Return ``(driver, owned)`` where ``owned`` means we created it and
        are responsible for closing it (the shared FakeDriver/DI instance is
        owned by the caller and persisted for the process)."""
        if self._driver is not None:
            return self._driver, False
        try:
            from graph.neo4j_client import create_driver, is_neo4j_healthy

            driver = create_driver()
            if driver is None or not is_neo4j_healthy(driver):
                if driver is not None:
                    try:
                        driver.close()
                    except Exception:
                        pass
                return None, False
            return driver, True
        except Exception:
            return None, False

    @staticmethod
    def _close_driver(driver) -> None:
        try:
            driver.close()
        except Exception:
            pass