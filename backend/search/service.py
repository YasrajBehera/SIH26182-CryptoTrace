"""Global search: cases, wallets, transactions, evidence, analyses, VASPs,
and reports. Each domain is queried through its owning repository so the
results reflect the same persisted data the other endpoints serve."""

from __future__ import annotations

from typing import List, Optional, Set

from cases.repository import (
    InvestigationRepository,
    make_investigation_repository,
)
from evidence.service import EvidenceService
from intelligence.service import VASPIntelligenceService
from search.models import SearchResult
from wallets.repository import WalletRepository, make_wallet_repository


class SearchService:
    def __init__(
        self,
        investigation_repository: Optional[InvestigationRepository] = None,
        wallet_repository: Optional[WalletRepository] = None,
        evidence_service: Optional[EvidenceService] = None,
        intelligence: Optional[VASPIntelligenceService] = None,
    ) -> None:
        self._cases = investigation_repository or make_investigation_repository()
        self._wallets = wallet_repository or make_wallet_repository()
        self._evidence = evidence_service or EvidenceService()
        self._intel = intelligence or VASPIntelligenceService()

    @staticmethod
    def _src(repo) -> str:
        return "postgres" if not getattr(repo, "is_demo", True) else "memory"

    def _case_results(self, needle: str, limit: int) -> List[SearchResult]:
        results: List[SearchResult] = []
        for case in self._cases.list({}):
            haystack = " ".join(
                [
                    case.get("id", ""),
                    case.get("name", ""),
                    case.get("primary_wallet", ""),
                    case.get("description", ""),
                ]
            ).lower()
            if needle in haystack:
                results.append(
                    SearchResult(
                        entity_type="investigation",
                        id=case.get("id", ""),
                        title=case.get("name", "Untitled investigation"),
                        subtitle=f"{case.get('status', 'open')} · "
                        f"{case.get('primary_wallet', '')[:10]}… "
                        f"· {case.get('risk', 'unknown')}",
                        url=f"/investigations/{case.get('id', '')}",
                        source=self._src(self._cases),
                        metadata={"wallet": case.get("primary_wallet", "")},
                    )
                )
        return results[:limit]

    def _wallet_results(self, needle: str, limit: int) -> List[SearchResult]:
        results: List[SearchResult] = []
        for summary in self._wallets.list_summaries():
            address = (summary.get("address") or "").lower()
            if needle in address:
                results.append(
                    SearchResult(
                        entity_type="wallet",
                        id=address,
                        title=address,
                        subtitle=(
                            f"{summary.get('chain', 'eth')} · "
                            f"{summary.get('risk', 'unknown')} · "
                            f"{summary.get('transaction_count', 0)} transfers"
                        ),
                        url=f"/wallets/{address}",
                        source=self._src(self._wallets),
                        metadata={"chain": summary.get("chain", "eth")},
                    )
                )
        return results[:limit]

    def _transaction_results(self, needle: str, limit: int) -> List[SearchResult]:
        results: List[SearchResult] = []
        for row in self._wallets.search_transactions(needle, limit):
            tx_hash = row.get("tx_hash", "")
            results.append(
                SearchResult(
                    entity_type="transaction",
                    id=tx_hash,
                    title=tx_hash,
                    subtitle=(
                        f"{row.get('chain', 'eth')} · "
                        f"{row.get('token_symbol') or 'native'}"
                    ),
                    url=f"/transactions?hash={tx_hash}",
                    source=self._src(self._wallets),
                    metadata={
                        "from": row.get("from_address", ""),
                        "to": row.get("to_address", ""),
                    },
                )
            )
        return results

    def _evidence_results(self, needle: str, limit: int) -> List[SearchResult]:
        results: List[SearchResult] = []
        repo = self._evidence.repository
        for record in self._evidence.search(needle, limit):
            evidence_id = record.evidence_id
            results.append(
                SearchResult(
                    entity_type="evidence",
                    id=evidence_id,
                    title=evidence_id,
                    subtitle=(
                        f"{record.evidence_type.value} · "
                        f"{record.address[:10]}… · {record.source}"
                    ),
                    url=f"/evidence?evidence_id={evidence_id}",
                    source=self._src(repo),
                    metadata={
                        "attribution_id": record.attribution_id,
                        "address": record.address,
                        "chain": record.chain,
                    },
                )
            )
        return results[:limit]

    def _attribution_results(
        self, needle: str, results_in: List[SearchResult], limit: int
    ) -> List[SearchResult]:
        """Analysis ids surface from real provenance: evidence records and
        persisted cases that carry a ``latest_analysis_id``."""
        seen: Set[str] = set()
        repo = self._evidence.repository
        for record in self._evidence.search(needle, limit):
            analysis_id = record.attribution_id
            if analysis_id and needle in analysis_id.lower() and analysis_id not in seen:
                seen.add(analysis_id)
                results_in.append(
                    SearchResult(
                        entity_type="attribution",
                        id=analysis_id,
                        title=analysis_id,
                        subtitle=(
                            f"{record.evidence_type.value} link · "
                            f"{record.address[:10]}… · {record.source}"
                        ),
                        url=f"/evidence?analysis_id={analysis_id}",
                        source=self._src(repo),
                        metadata={
                            "address": record.address,
                            "chain": record.chain,
                        },
                    )
                )
        for case in self._cases.list({}):
            analysis_id = case.get("latest_analysis_id")
            if analysis_id and needle in analysis_id.lower() and analysis_id not in seen:
                seen.add(analysis_id)
                results_in.append(
                    SearchResult(
                        entity_type="attribution",
                        id=analysis_id,
                        title=analysis_id,
                        subtitle=f"latest analysis · {case.get('name', '')}",
                        url=f"/evidence?analysis_id={analysis_id}",
                        source=self._src(self._cases),
                        metadata={
                            "case_id": case.get("id", ""),
                            "address": case.get("primary_wallet", ""),
                        },
                    )
                )
        return results_in

    def _vasp_results(self, needle: str, limit: int) -> List[SearchResult]:
        # Only the curated PUBLIC directory surfaces here; the synthetic seed
        # is never presented as fact.
        repo = self._intel.repository_for("live")
        results: List[SearchResult] = []
        for entity in repo.get_all_entities():
            name = entity.name
            if needle in name.lower():
                results.append(
                    SearchResult(
                        entity_type="vasp",
                        id=name,
                        title=name,
                        subtitle=f"{entity.entity_type} · {entity.jurisdiction}",
                        url=f"/vasp?entity={name}",
                        source="curated",
                        metadata={"jurisdiction": entity.jurisdiction},
                    )
                )
        for addr in repo.get_all_addresses():
            name = addr.vasp_name
            if needle in name.lower():
                results.append(
                    SearchResult(
                        entity_type="vasp",
                        id=name,
                        title=f"{name} · {addr.address[:10]}…",
                        subtitle=(
                            f"{addr.chain} · {addr.verification_status.value} "
                            f"· {addr.source}"
                        ),
                        url=f"/wallets/{addr.address}",
                        source="curated",
                        metadata={
                            "address": addr.address,
                            "chain": addr.chain,
                        },
                    )
                )
        return results[:limit]

    def search(
        self,
        q: str,
        limit: int = 20,
        entity_types: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        needle = (q or "").strip().lower()
        if not needle:
            return []
        requested = set(entity_types or [])
        def wants(t: str) -> bool:
            return not requested or t in requested

        pool: List[SearchResult] = []
        if wants("investigation"):
            pool.extend(self._case_results(needle, limit))
        if wants("wallet"):
            pool.extend(self._wallet_results(needle, limit))
        if wants("transaction"):
            pool.extend(self._transaction_results(needle, limit))
        if wants("evidence"):
            pool.extend(self._evidence_results(needle, limit))
        if wants("attribution"):
            self._attribution_results(needle, pool, limit)
        if wants("vasp"):
            pool.extend(self._vasp_results(needle, limit))
        if wants("report"):
            pool.extend(self._report_results(needle, limit))

        seen: Set[tuple] = set()
        unique: List[SearchResult] = []
        for result in pool:
            key = (result.entity_type, result.id)
            if key in seen:
                continue
            seen.add(key)
            unique.append(result)

        unique.sort(
            key=lambda r: (
                0 if r.id.lower().startswith(needle) else 1,
                r.title.lower(),
            )
        )
        return unique[:limit]

    def _report_results(self, needle: str, limit: int) -> List[SearchResult]:
        """Reports are surfaced from the audit trail (REPORT_EXPORT events,
        which carry the generated report id and the case id) and from case
        ``latest_report_ids``. No report data is fabricated."""
        results: List[SearchResult] = []
        seen: Set[str] = set()
        for case in self._cases.list({}):
            case_id = case.get("id", "")
            for report_id in case.get("latest_report_ids") or []:
                if (
                    report_id not in seen
                    and (needle in report_id.lower() or needle in case_id.lower())
                ):
                    seen.add(report_id)
                    results.append(
                        SearchResult(
                            entity_type="report",
                            id=report_id,
                            title=f"Report {report_id}",
                            subtitle=f"case {case_id} · {case.get('name', '')}",
                            url="/reports",
                            source=self._src(self._cases),
                            metadata={"case_id": case_id},
                        )
                    )
        return results[:limit]