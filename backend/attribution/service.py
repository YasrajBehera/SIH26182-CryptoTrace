import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from attribution.models import (
    AttributionCandidate,
    AttributionRequest,
    AttributionResponse,
    Confidence,
    ScoreBreakdown,
)
from attribution.scoring import AttributionScorer, ScoringWeights
from blockchain.chains import canonical_chain, normalize_address
from blockchain.chains import CHAIN_REGISTRY
from evidence.models import EvidenceRecord, EvidenceType
from evidence.service import EvidenceService
from intelligence.models import VASPAddress, VerificationStatus
from intelligence.repository import VASPRepository
from intelligence.service import VASPIntelligenceService

#: Attached to every directory-match evidence record. A curated address label
#: is a lead, not a legal determination, and the record has to say so wherever
#: it is read.
_OWNERSHIP_DISCLAIMER = (
    "A public directory label is an investigative lead. It does not by itself "
    "establish legal ownership, control, or the identity of the operator."
)


@dataclass(frozen=True)
class _Component:
    score: float
    explanations: List[str]


def _score_components(
    scorer: AttributionScorer,
    address: str,
    chain: str,
    neighbor_wallet_ids: List[str],
    path_data: Optional[Dict],
    graph_data: Optional[Dict],
) -> Dict[EvidenceType, _Component]:
    """Run every scorer once and collect the results.

    Kept as a single pass so the scores, their order and their wording cannot
    drift between candidates.
    """
    graph_score, graph_expl = scorer.score_graph_proximity(
        address, chain, neighbor_wallet_ids, path_data
    )
    known_score, known_expl = scorer.score_known_address_match(
        address, chain, graph_data
    )
    temporal_score, temporal_expl = scorer.score_temporal_consistency(
        address, chain, graph_data
    )
    flow_score, flow_expl = scorer.score_transaction_flow(address, chain, graph_data)
    cluster_score, cluster_expl = scorer.score_cluster_evidence(
        address, chain, graph_data
    )
    return {
        EvidenceType.GRAPH_PROXIMITY: _Component(graph_score, graph_expl),
        EvidenceType.KNOWN_ADDRESS_MATCH: _Component(known_score, known_expl),
        EvidenceType.TEMPORAL_CONSISTENCY: _Component(temporal_score, temporal_expl),
        EvidenceType.TRANSACTION_FLOW: _Component(flow_score, flow_expl),
        EvidenceType.CLUSTER_EVIDENCE: _Component(cluster_score, cluster_expl),
    }


class AttributionService:
    def __init__(
        self,
        vasp_intelligence: Optional[VASPIntelligenceService] = None,
        evidence_service: Optional[EvidenceService] = None,
        weights: Optional[ScoringWeights] = None,
    ) -> None:
        self._intel = vasp_intelligence or VASPIntelligenceService()
        self._evidence = evidence_service or EvidenceService()
        self._scorer = AttributionScorer(
            vasp_repo=self._intel.repository,
            evidence_svc=self._evidence,
            weights=weights,
        )

    @property
    def scorer(self) -> AttributionScorer:
        return self._scorer

    @property
    def evidence_service(self) -> EvidenceService:
        return self._evidence

    @property
    def intelligence_service(self) -> VASPIntelligenceService:
        return self._intel

    def _determine_confidence(self, score: float) -> Confidence:
        if score >= AttributionScorer.HIGH_THRESHOLD:
            return Confidence.HIGH
        elif score >= AttributionScorer.MEDIUM_THRESHOLD:
            return Confidence.MEDIUM
        return Confidence.LOW

    def _build_graph_data_for_address(
        self,
        address: str,
        chain: str,
        graph_data: Optional[Dict],
    ) -> Tuple[List[str], Optional[Dict]]:
        neighbor_wallet_ids: List[str] = []
        enriched: Dict = dict(graph_data) if graph_data else {}

        if graph_data:
            bfs_nodes = graph_data.get("bfs", {}).get("nodes", [])
            for node in bfs_nodes:
                wid = node.get("wallet_id", "")
                if wid:
                    neighbor_wallet_ids.append(wid)
            if not neighbor_wallet_ids:
                for node in graph_data.get("neighbors", []):
                    wid = node.get("wallet_id", "")
                    if wid:
                        neighbor_wallet_ids.append(wid)

        return neighbor_wallet_ids, enriched

    @staticmethod
    def _evidence_source(data_source: str) -> str:
        """Evidence provenance reflects how the analysis was derived. Chain
        evidence comes from real transaction data; everything else is synthetic
        (demo). Never conflate the two."""
        return "chain" if data_source == "live" else "synthetic"

    @staticmethod
    def _chain_label(chain: str) -> str:
        spec = CHAIN_REGISTRY.get(canonical_chain(chain))
        return spec.label if spec else chain

    def _matched_directory_entry(
        self,
        address: str,
        chain: str,
        repo: VASPRepository,
    ) -> Optional[VASPAddress]:
        """The verified directory entry this exact wallet matches, if any.

        Matching is strictly ``(chain, normalized address)``. A valid-looking hex
        string on another chain is a different account and never matches.
        """
        verified = {
            normalize_address(entry.address)
            for entry in repo.get_known_vasp_addresses(canonical_chain(chain))
        }
        target = normalize_address(address)
        if target not in verified:
            return None
        matches = [
            entry
            for entry in repo.lookup_by_address(address, chain)
            if entry.verification_status == VerificationStatus.VERIFIED
        ]
        return max(matches, key=lambda m: m.confidence) if matches else None

    def _vasp_counterparties(
        self,
        address: str,
        chain: str,
        graph_data: Optional[Dict],
        repo: VASPRepository,
    ) -> List[Dict]:
        """Observed transactions between this wallet and a verified VASP address.

        Every field returned is read straight out of the ingested transfers, so
        a transaction hash, direction, amount or asset can only ever appear here
        if the chain actually produced it. Nothing is inferred or filled in.
        """
        if not graph_data:
            return []

        canonical = canonical_chain(chain)
        known = {
            normalize_address(entry.address): entry
            for entry in repo.get_known_vasp_addresses(canonical)
        }
        if not known:
            return []

        wallet = f"{canonical}:{normalize_address(address)}"
        found: List[Dict] = []
        seen = set()

        flows = graph_data.get("flows") or []
        for flow in flows:
            src = (flow.get("source") or "").strip()
            tgt = (flow.get("target") or "").strip()
            if src == wallet:
                counterpart, direction = tgt, "out"
            elif tgt == wallet:
                counterpart, direction = src, "in"
            else:
                continue
            raw_address = counterpart.split(":", 1)[-1]
            entry = known.get(normalize_address(raw_address))
            if entry is None:
                continue

            tx_hash = (flow.get("tx_hash") or "").strip()
            key = (tx_hash, direction, entry.address.lower())
            if key in seen:
                continue
            seen.add(key)
            found.append(
                {
                    "vasp_name": entry.vasp_name,
                    "address": entry.address,
                    "tx_hash": tx_hash or None,
                    "direction": direction,
                    "amount": flow.get("amount"),
                    "asset": flow.get("asset") or "",
                    "timestamp": flow.get("timestamp"),
                    "source": entry.source,
                    "source_url": entry.source_url,
                }
            )

        found.sort(key=lambda item: (item["timestamp"] or 0, item["tx_hash"] or ""))
        return found

    @staticmethod
    def _describe_counterparty(item: Dict) -> str:
        """One human-readable line per observed VASP-counterparty transaction."""
        chain_part = ""
        value = item.get("amount")
        asset = item.get("asset")
        if value not in (None, ""):
            chain_part = f" {value}" + (f" {asset}" if asset else "")
        elif asset:
            chain_part = f" {asset}"
        parts = [
            f"{item['vasp_name']} ({item['address']})",
            f"direction {item['direction']}",
        ]
        if chain_part:
            parts.append(f"value{chain_part}")
        if item.get("tx_hash"):
            parts.append(f"tx {item['tx_hash']}")
        if item.get("source"):
            parts.append(f"source {item['source']}")
        return ", ".join(parts)

    def _directory_match_evidence(
        self,
        analysis_id: str,
        address: str,
        chain: str,
        entry: VASPAddress,
        score: float,
        base_description: str,
        data_source: str,
    ) -> EvidenceRecord:
        """Evidence for "this wallet IS a publicly labelled VASP address".

        Recorded on ``chain`` only. The directory's verification transaction is
        cited as label provenance and is explicitly labelled as such, because it
        attests the label and not any relationship with the investigated wallet.
        """
        label = self._chain_label(chain)
        description = (
            f"{base_description} {entry.vasp_name} is publicly labelled on "
            f"{label} at {entry.address}. "
            f"Directory source: {entry.source}"
            + (f" ({entry.source_url})" if entry.source_url else "")
            + f". Verification status: {entry.verification_status.value}."
        )
        if entry.evidence:
            description += f" Verification: {entry.evidence}"
        if entry.verification_tx_hash:
            description += (
                f" Label verified against {label} transaction "
                f"{entry.verification_tx_hash}"
                + (
                    f" in block {entry.verification_block}"
                    if entry.verification_block
                    else ""
                )
                + "; that transaction attests the public label only and is not "
                "evidence of any transfer to or from the investigated wallet."
            )
        return self._evidence.create_evidence(
            attribution_id=analysis_id,
            evidence_type=EvidenceType.KNOWN_ADDRESS_MATCH,
            address=address,
            chain=chain,
            confidence=score / 100.0,
            description=description,
            method="attribution_engine_v1",
            source=self._evidence_source(data_source),
            matched_address=entry.address,
            limitations=[
                _OWNERSHIP_DISCLAIMER,
                f"Label verified against {label} transaction "
                f"{entry.verification_tx_hash}"
                + (
                    f" in block {entry.verification_block}"
                    if entry.verification_block
                    else ""
                )
                + "; that transaction attests the public label only and is not "
                "evidence of any transfer to or from the investigated wallet.",
                f"Label applies to {label} only; the same address string on "
                "another chain is a different account and was not matched.",
                "The directory is a small curated reference set, not an "
                "exhaustive registry of VASP-controlled wallets.",
            ],
        )

    def _counterparty_evidence(
        self,
        analysis_id: str,
        address: str,
        chain: str,
        evidence_type: EvidenceType,
        counterparties: List[Dict],
        score: float,
        base_description: str,
        data_source: str,
        graph_path: Optional[List[str]] = None,
    ) -> EvidenceRecord:
        """Evidence that this wallet actually transacted with a verified VASP.

        The first observed transaction is used as the record's ``tx_hash`` so the
        evidence is clickable back to the chain; every observed transaction is
        listed in the description so nothing is hidden behind that choice.
        """
        label = self._chain_label(chain)
        observed = "; ".join(self._describe_counterparty(item) for item in counterparties)
        description = (
            f"{base_description} Observed on {label}: {observed}."
            if observed
            else f"{base_description} No transaction with a verified VASP address "
            "on this chain was observed in the ingested data."
        )
        if graph_path:
            description += f" Graph path: {' -> '.join(graph_path)}."
        # Counterparty detail is only attached when a transaction was actually
        # observed, so a behavioural score can never borrow another record's tx.
        primary = counterparties[0] if counterparties else None
        return self._evidence.create_evidence(
            attribution_id=analysis_id,
            evidence_type=evidence_type,
            address=address,
            chain=chain,
            confidence=score / 100.0,
            description=description,
            method="attribution_engine_v1",
            source=self._evidence_source(data_source),
            tx_hash=primary.get("tx_hash") if primary else None,
            timestamp=primary.get("timestamp") if primary else None,
            graph_path=graph_path,
            matched_address=primary["address"] if primary else None,
            limitations=[
                _OWNERSHIP_DISCLAIMER,
                "A transaction with a publicly labelled address is a "
                "transactional association, not proof that the VASP controlled "
                "the sending or receiving wallet.",
                "Only the scanned block range is covered; earlier history may "
                "exist that was not ingested.",
            ],
        )

    def _build_evidence(
        self,
        *,
        analysis_id: str,
        evidence_type: EvidenceType,
        address: str,
        chain: str,
        score: float,
        base_description: str,
        directory_entry: Optional[VASPAddress],
        counterparties: List[Dict],
        graph_path: Optional[List[str]],
        data_source: str,
    ) -> EvidenceRecord:
        """Create one evidence record, enriched wherever real detail exists.

        Behavioural signals (temporal regularity, clustering) describe the
        wallet itself, so they stay as the scorer worded them. Only the two
        evidence types that point at a counterparty are enriched, and only with
        values that came out of the ingested chain data or the curated directory.
        Every record still states its own limitations.
        """
        label = self._chain_label(chain)
        if evidence_type == EvidenceType.KNOWN_ADDRESS_MATCH:
            if directory_entry:
                return self._directory_match_evidence(
                    analysis_id=analysis_id,
                    address=address,
                    chain=chain,
                    entry=directory_entry,
                    score=score,
                    base_description=base_description,
                    data_source=data_source,
                )
            # No directory match, but the component only scores above zero when
            # real transfers with a verified VASP address were observed. The
            # record must name that VASP and those transactions, otherwise the
            # score would assert an association the evidence does not describe.
            if counterparties:
                return self._counterparty_evidence(
                    analysis_id=analysis_id,
                    address=address,
                    chain=chain,
                    evidence_type=evidence_type,
                    counterparties=counterparties,
                    score=score,
                    base_description=base_description,
                    data_source=data_source,
                    graph_path=None,
                )
        if evidence_type in (
            EvidenceType.GRAPH_PROXIMITY,
            EvidenceType.TRANSACTION_FLOW,
        ):
            return self._counterparty_evidence(
                analysis_id=analysis_id,
                address=address,
                chain=chain,
                evidence_type=evidence_type,
                counterparties=counterparties,
                score=score,
                base_description=base_description,
                data_source=data_source,
                graph_path=graph_path if evidence_type == EvidenceType.GRAPH_PROXIMITY else None,
            )
        return self._evidence.create_evidence(
            attribution_id=analysis_id,
            evidence_type=evidence_type,
            address=address,
            chain=chain,
            confidence=score / 100.0,
            description=base_description,
            method="attribution_engine_v1",
            source=self._evidence_source(data_source),
            limitations=[
                _OWNERSHIP_DISCLAIMER,
                self._component_caveat(evidence_type, label),
                "Only the scanned block range is covered; earlier history may "
                "exist that was not ingested.",
            ],
        )

    @staticmethod
    def _component_caveat(evidence_type: EvidenceType, label: str) -> str:
        """What one scoring component can and cannot establish on its own.

        Every evidence record must state its own limits; a behavioural component
        that never names a VASP address is the weakest possible evidence of
        association and must say so rather than let a non-zero score imply it.
        """
        if evidence_type is EvidenceType.TEMPORAL_CONSISTENCY:
            return (
                "Timing regularity describes this wallet's behaviour, not any "
                f"specific VASP on {label}; it links the wallet to nothing on its "
                "own and only supports a score that also has a VASP-specific "
                "signal."
            )
        if evidence_type is EvidenceType.CLUSTER_EVIDENCE:
            return (
                "Cluster membership is a heuristic grouping, not proof that the "
                "entities in it are controlled by the same operator."
            )
        if evidence_type is EvidenceType.KNOWN_ADDRESS_MATCH:
            return (
                "No VASP address matched this wallet on "
                f"{label}; this component contributed no VASP-specific signal."
            )
        return (
            "This component describes the wallet's on-chain behaviour on "
            f"{label} and does not by itself identify who controls it."
        )

    def analyze(
        self,
        request: AttributionRequest,
        *,
        data_source: str = "demo",
    ) -> AttributionResponse:
        address = request.address.lower()
        chain = request.chain
        analysis_id = f"attr-{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        neighbor_wallet_ids, graph_data = self._build_graph_data_for_address(
            address, chain, request.graph_data
        )

        # Select the reference directory that matches the analysis source. A
        # live investigation is scored against the curated PUBLIC directory;
        # demo analyses keep the synthetic seed so tests stay hermetic.
        repo = self._intel.repository_for(data_source)
        scorer = (
            self._scorer
            if data_source != "live"
            else AttributionScorer(
                vasp_repo=repo,
                evidence_svc=self._evidence,
                weights=self._scorer.weights,
            )
        )

        path_data = graph_data.get("path") if graph_data else None
        candidate_vasps = self._collect_candidate_vasps(address, chain, repo)

        # Traceability inputs, resolved once for the whole analysis. They change
        # only what the evidence records *say* - never the scores, which stay
        # exactly what the scorer produced.
        directory_entry = self._matched_directory_entry(address, chain, repo)
        counterparties = self._vasp_counterparties(address, chain, graph_data, repo)
        graph_path = list(path_data.get("path", [])) if path_data else None

        candidates: List[AttributionCandidate] = []
        # Component scores are identical for every candidate VASP (they describe
        # the wallet), so they are computed once and reused.
        components = _score_components(
            scorer=scorer,
            address=address,
            chain=chain,
            neighbor_wallet_ids=neighbor_wallet_ids,
            path_data=path_data,
            graph_data=graph_data,
        )
        w = scorer.weights
        total_score = max(
            0.0,
            min(
                100.0,
                sum(
                    components[ev_type].score * getattr(w, ev_type.value)
                    for ev_type in components
                ),
            ),
        )
        explanations: List[str] = []
        for ev_type, component in components.items():
            explanations.extend(component.explanations)

        for vasp_name in candidate_vasps:
            candidates.append(
                AttributionCandidate(
                    address=address,
                    chain=chain,
                    vasp_name=vasp_name,
                    score=round(total_score, 2),
                    confidence=self._determine_confidence(total_score),
                    evidence_ids=[],
                    score_breakdown=ScoreBreakdown(
                        **{
                            ev_type.value: component.score
                            for ev_type, component in components.items()
                        }
                    ),
                    explanation=list(explanations),
                )
            )

        candidates.sort(key=lambda c: c.score, reverse=True)

        # Only candidates with a real attribution signal are surfaced. A
        # scored address directory entry always lands above zero, so a genuine
        # known-address match survives; the bulk of the public directory that
        # merely shares a chain is noise. When nothing scores, the UNKNOWN
        # placeholder keeps the contract explicit ("no evidence of this wallet
        # belonging to a VASP") without fabricating a ranking.
        candidates = [
            c
            for c in candidates
            if c.score > 0 and self._is_relevant_candidate(c, directory_entry, counterparties)
        ]

        if not candidates:
            candidates.append(
                AttributionCandidate(
                    address=address,
                    chain=chain,
                    vasp_name="UNKNOWN",
                    score=0.0,
                    confidence=Confidence.LOW,
                    evidence_ids=[],
                    score_breakdown=ScoreBreakdown(),
                    explanation=[self._no_candidate_reason(repo, chain)],
                )
            )

        # Evidence is minted only for candidates that survive the filter above,
        # so every retrievable evidence record belongs to a candidate the caller
        # can actually see. An orphan record would otherwise describe a finding
        # that the response never presents.
        for candidate in candidates:
            if candidate.vasp_name == "UNKNOWN":
                continue
            candidate.evidence_ids = [
                self._build_evidence(
                    analysis_id=analysis_id,
                    evidence_type=ev_type,
                    address=address,
                    chain=chain,
                    score=component.score,
                    base_description="; ".join(component.explanations),
                    directory_entry=directory_entry,
                    counterparties=counterparties,
                    graph_path=graph_path,
                    data_source=data_source,
                ).evidence_id
                for ev_type, component in components.items()
                if component.score > 0
            ]

        return AttributionResponse(
            address=address,
            chain=chain,
            candidates=candidates,
            analysis_id=analysis_id,
            timestamp=timestamp,
        )

    @staticmethod
    def _is_relevant_candidate(
        candidate: AttributionCandidate,
        directory_entry: Optional[VASPAddress],
        counterparties: List[Dict],
    ) -> bool:
        """Keep a scored candidate only when a VASP-specific signal exists.

        The behavioural components (temporal regularity, counterparty count)
        score the *wallet*, not the (wallet, VASP) pair, so they produce the
        same score for every VASP that merely shares the chain. On a chain with
        a single verified VASP address that turns into a lone, confident-looking
        row for a VASP the wallet has never touched. A candidate is therefore
        surfaced only when the wallet itself is that VASP's directory address on
        this chain, or when a real transaction with that VASP's verified address
        on this chain was observed.

        This is a relevance filter on the existing ``score > 0`` rule; it does
        not alter any score, weight or threshold.
        """
        if directory_entry is not None and directory_entry.vasp_name == candidate.vasp_name:
            return True
        return any(
            item["vasp_name"] == candidate.vasp_name
            and normalize_address(item["address"]) != normalize_address(candidate.address)
            for item in counterparties
        )

    def _no_candidate_reason(self, repo, chain: str) -> str:
        """Explain an empty candidate set without implying the wallet is clean."""
        if not repo.get_vasp_names_for_chain(chain):
            return (
                f"No VASP candidates: the reference directory contains no "
                f"verified addresses for '{chain}', so no VASP can be proposed "
                "for this wallet from the available evidence. This is a data "
                "coverage gap, not a finding that the wallet is not a VASP."
            )
        return "No VASP candidates found for this address"

    def _collect_candidate_vasps(
        self, address: str, chain: str, repo
    ) -> List[str]:
        """Entities that can legitimately be considered for ``chain``.

        Only VASPs that actually have a directory entry on the investigated chain
        are candidates. Falling back to every known entity used to rank an
        arbitrary VASP (alphabetically first among ties) for any chain the
        directory does not cover, which presented an Ethereum exchange as a
        candidate for a Ronin wallet purely because both are "a chain we know
        something about". No evidence links them, so they are not candidates.
        """
        return sorted(set(repo.get_vasp_names_for_chain(chain)))
