import uuid
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
from evidence.models import EvidenceType
from evidence.service import EvidenceService
from intelligence.repository import VASPRepository
from intelligence.service import VASPIntelligenceService


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

    def analyze(self, request: AttributionRequest) -> AttributionResponse:
        address = request.address.lower()
        chain = request.chain
        analysis_id = f"attr-{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        neighbor_wallet_ids, graph_data = self._build_graph_data_for_address(
            address, chain, request.graph_data
        )

        path_data = graph_data.get("path") if graph_data else None
        candidate_vasps = self._collect_candidate_vasps(address, chain)

        candidates: List[AttributionCandidate] = []

        for vasp_name in candidate_vasps:
            evidence_ids: List[str] = []
            explanations: List[str] = []
            breakdown = ScoreBreakdown()

            s_graph, e_graph = self._scorer.score_graph_proximity(
                address, chain, neighbor_wallet_ids, path_data
            )
            breakdown.graph_proximity = s_graph
            explanations.extend(e_graph)

            s_known, e_known = self._scorer.score_known_address_match(
                address, chain
            )
            breakdown.known_address_match = s_known
            explanations.extend(e_known)

            s_temporal, e_temporal = self._scorer.score_temporal_consistency(
                address, chain, graph_data
            )
            breakdown.temporal_consistency = s_temporal
            explanations.extend(e_temporal)

            s_flow, e_flow = self._scorer.score_transaction_flow(
                address, chain, graph_data
            )
            breakdown.transaction_flow = s_flow
            explanations.extend(e_flow)

            s_cluster, e_cluster = self._scorer.score_cluster_evidence(
                address, chain, graph_data
            )
            breakdown.cluster_evidence = s_cluster
            explanations.extend(e_cluster)

            w = self._scorer.weights
            total_score = (
                s_graph * w.graph_proximity
                + s_known * w.known_address_match
                + s_temporal * w.temporal_consistency
                + s_flow * w.transaction_flow
                + s_cluster * w.cluster_evidence
            )
            total_score = max(0.0, min(100.0, total_score))

            for ev_type, score, desc in [
                (EvidenceType.GRAPH_PROXIMITY, s_graph, e_graph),
                (EvidenceType.KNOWN_ADDRESS_MATCH, s_known, e_known),
                (EvidenceType.TEMPORAL_CONSISTENCY, s_temporal, e_temporal),
                (EvidenceType.TRANSACTION_FLOW, s_flow, e_flow),
                (EvidenceType.CLUSTER_EVIDENCE, s_cluster, e_cluster),
            ]:
                if score > 0:
                    record = self._evidence.create_evidence(
                        attribution_id=analysis_id,
                        evidence_type=ev_type,
                        address=address,
                        chain=chain,
                        confidence=score / 100.0,
                        description="; ".join(desc),
                        method="attribution_engine_v1",
                    )
                    evidence_ids.append(record.evidence_id)

            candidates.append(
                AttributionCandidate(
                    address=address,
                    chain=chain,
                    vasp_name=vasp_name,
                    score=round(total_score, 2),
                    confidence=self._determine_confidence(total_score),
                    evidence_ids=evidence_ids,
                    score_breakdown=breakdown,
                    explanation=explanations,
                )
            )

        candidates.sort(key=lambda c: c.score, reverse=True)

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
                    explanation=["No VASP candidates found for this address"],
                )
            )

        return AttributionResponse(
            address=address,
            chain=chain,
            candidates=candidates,
            analysis_id=analysis_id,
            timestamp=timestamp,
        )

    def _collect_candidate_vasps(
        self, address: str, chain: str
    ) -> List[str]:
        vasp_names = self._intel.repository.get_vasp_names_for_chain(chain)
        if not vasp_names:
            vasp_names = [e.name for e in self._intel.repository.get_all_entities()]
        return sorted(set(vasp_names))
