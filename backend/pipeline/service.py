from typing import Optional

from attribution.adapter import build_graph_data
from attribution.models import AttributionRequest
from attribution.service import AttributionService
from graph.builder import TransactionGraph
from graph.temporal import fund_flow as compute_fund_flow
from graph.temporal import temporal_path as compute_temporal_path
from intelligence.service import VASPIntelligenceService
from pipeline.models import InvestigationRequest, InvestigationResult


class InvestigationPipeline:
    def __init__(self) -> None:
        self._intel = VASPIntelligenceService()
        self._attr = AttributionService(vasp_intelligence=self._intel)

    @property
    def attribution_service(self) -> AttributionService:
        return self._attr

    @property
    def intelligence_service(self) -> VASPIntelligenceService:
        return self._intel

    def _synth_txs_to_graph(
        self, synth_txs, target_address: str
    ) -> TransactionGraph:
        graph = TransactionGraph()
        for tx in synth_txs:
            graph.add_edge(
                chain=tx.chain,
                tx_hash=tx.tx_hash,
                sender_address=tx.from_address,
                receiver_address=tx.to_address,
                amount=__import__("decimal").Decimal(tx.value),
                timestamp=tx.block_timestamp,
            )
        return graph

    def _graph_to_graph_data(
        self,
        graph: TransactionGraph,
        address: str,
        chain: str,
    ) -> dict:
        wallet_id = f"{chain}:{address.lower()}"
        neighbors = graph.neighbors(wallet_id)

        bfs_dict = {
            "wallet_id": wallet_id,
            "max_depth": 3,
            "nodes": [
                {
                    "wallet_id": nid,
                    "address": nid.split(":", 1)[-1],
                    "chain": chain,
                    "depth": 1,
                }
                for nid in neighbors
            ],
        }

        all_nodes = [n["wallet_id"] for n in graph.nodes]
        target_wid = None
        for other in all_nodes:
            if other != wallet_id:
                result = graph.bfs_path(wallet_id, other)
                if result.get("found"):
                    target_wid = other
                    break

        path_dict = None
        if target_wid:
            bfs_path_result = graph.bfs_path(wallet_id, target_wid)
            path_dict = {
                "source": bfs_path_result.get("source", wallet_id),
                "destination": bfs_path_result.get("destination", target_wid),
                "path": bfs_path_result.get("path", []),
                "hop_count": bfs_path_result.get("hop_count"),
                "found": bfs_path_result.get("found", False),
            }

        edges_out = graph.get_edges_from(wallet_id)
        edges_in = graph.get_edges_to(wallet_id)
        all_edges = edges_out + edges_in

        flows_for_temporal = [
            {
                "tx_hash": e.tx_hash,
                "chain": e.chain,
                "source": e.sender,
                "target": e.receiver,
                "amount": str(e.amount),
                "timestamp": e.timestamp,
            }
            for e in sorted(all_edges, key=lambda x: x.timestamp)
        ]

        temporal_flow_dict = {
            "wallet_id": wallet_id,
            "direction": "all",
            "flows": flows_for_temporal,
        }

        graph_data = build_graph_data(
            bfs=bfs_dict,
            path=path_dict,
            temporal_flow=temporal_flow_dict,
        )

        return graph_data

    def run(
        self,
        request: InvestigationRequest,
        synth_txs=None,
    ) -> InvestigationResult:
        address = request.address.lower()
        chain = request.chain

        if synth_txs is None:
            from graph.synthetic import generate_transactions

            synth_txs = generate_transactions(seed=42, count=30)

        graph = self._synth_txs_to_graph(synth_txs, address)

        graph_data = self._graph_to_graph_data(graph, address, chain)

        intel = self._intel.lookup_address(address, chain)

        attr_request = AttributionRequest(
            address=address,
            chain=chain,
            graph_data=graph_data,
        )
        attr_response = self._attr.analyze(attr_request)

        evidence_count = 0
        for c in attr_response.candidates:
            evidence_count += len(c.evidence_ids)

        return InvestigationResult(
            address=address,
            chain=chain,
            transfers_ingested=len(synth_txs),
            graph_nodes=graph.node_count,
            graph_edges=graph.edge_count,
            address_intelligence=intel,
            candidates=attr_response.candidates,
            analysis_id=attr_response.analysis_id,
            evidence_count=evidence_count,
        )
