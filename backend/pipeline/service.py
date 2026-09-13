import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from attribution.adapter import build_graph_data
from attribution.api import get_attribution_service
from attribution.models import AttributionRequest
from attribution.service import AttributionService
from graph.builder import TransactionGraph
from graph.temporal import fund_flow as compute_fund_flow
from graph.temporal import temporal_path as compute_temporal_path
from pipeline.models import InvestigationRequest, InvestigationResult
from wallets.service import WalletService


class InvestigationPipeline:
    """Investigation pipeline that shares the app-wide attribution service.

    Sharing the AttributionService singleton (and its EvidenceService) is
    required so that evidence records created by POST .../analyze are actually
    retrievable through the evidence service endpoints (GET /api/v1/evidence/*).

    Data sourcing is always explicit:
      - ``live``  transfers came from the blockchain provider (Alchemy)
      - ``demo``  synthetic transfers were generated locally (offline fallback)
    """

    def __init__(self, *, sync_to_neo4j: bool = True) -> None:
        self._attr = get_attribution_service()
        self._intel = self._attr.intelligence_service
        self._wallets = WalletService()
        self._sync_to_neo4j = sync_to_neo4j

    @property
    def attribution_service(self) -> AttributionService:
        return self._attr

    @property
    def intelligence_service(self):
        return self._intel

    @staticmethod
    def _tx_field(tx, *names, default=None):
        """Read a field by any accepted name (synthetic/graph use ``tx_hash``,
        normalized blockchain transfers use ``transaction_hash``)."""
        if isinstance(tx, dict):
            for name in names:
                if name in tx:
                    return tx[name]
            return default
        for name in names:
            if hasattr(tx, name):
                return getattr(tx, name)
        return default

    def _transfers_to_graph(
        self, transfers, target_address: str
    ) -> TransactionGraph:
        graph = TransactionGraph()
        for tx in transfers:
            block_timestamp = self._tx_field(tx, "block_timestamp")
            if block_timestamp is None:
                block_timestamp = 0
            elif not isinstance(block_timestamp, int):
                block_timestamp = int(block_timestamp.timestamp())
            graph.add_edge(
                chain=self._tx_field(tx, "chain", default="eth"),
                tx_hash=self._tx_field(tx, "tx_hash", "transaction_hash"),
                sender_address=self._tx_field(tx, "from_address", "sender_address"),
                receiver_address=self._tx_field(tx, "to_address", "receiver_address"),
                amount=Decimal(self._tx_field(tx, "value")),
                timestamp=block_timestamp,
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

    def _to_wallet_rows(self, transfers) -> List[dict]:
        """Normalize blockchain transfers into the agreed wallet-store row shape."""
        rows: List[dict] = []
        for t in transfers:
            ts = t.block_timestamp
            if hasattr(ts, "timestamp"):
                ts = int(ts.timestamp())
            rows.append(
                {
                    "chain": self._tx_field(t, "chain", default="eth"),
                    "tx_hash": self._tx_field(t, "transaction_hash", "tx_hash"),
                    "block_number": self._tx_field(t, "block_number"),
                    "block_timestamp": ts,
                    "from_address": self._tx_field(t, "from_address", "sender_address"),
                    "to_address": self._tx_field(t, "to_address", "receiver_address"),
                    "value": str(self._tx_field(t, "value")),
                    "fee": None,
                    "token_symbol": self._tx_field(t, "asset", "token_symbol"),
                }
            )
        return rows

    def _try_live(self, request: InvestigationRequest):
        """Fetch REAL transfers from the blockchain provider.

        Returns (transfers, data_source) or (None, "demo") when the provider is
        unavailable/misconfigured/the address is not a valid Ethereum address.
        """
        if request.chain != "eth":
            return None, "demo"
        from blockchain.service import BlockchainService

        service = BlockchainService()
        try:
            result = asyncio.run(
                service.get_wallet_transfers(
                    request.address, chain=request.chain, limit=request.limit or 200
                )
            )
        except Exception:
            return None, "demo"
        if not result.transfers:
            return None, "demo"
        return result.transfers, "live"

    def _sync_live_to_neo4j(self, wallet_rows: List[dict]) -> int:
        """Best-effort mirror of freshly ingested LIVE rows into Neo4j.

        Runs only for real chain data so the graph reflects the investigation
        without requiring a manual ``POST /api/v1/graph/sync``. Failures and
        an unreachable Neo4j are tolerated: GraphPage reports engine
        availability independently, and a manual sync can always be triggered.
        """
        if not wallet_rows:
            return 0
        try:
            from graph.neo4j_client import create_driver, is_neo4j_healthy
            from graph import service as graph_service

            driver = create_driver()
        except Exception:
            return 0
        try:
            if not is_neo4j_healthy(driver):
                return 0
            return graph_service.merge_transactions(driver, wallet_rows)
        except Exception:
            return 0
        finally:
            driver.close()

    def run(
        self,
        request: InvestigationRequest,
        synth_txs=None,
    ) -> InvestigationResult:
        address = request.address.lower()
        chain = request.chain

        data_source = "demo"
        wallet_rows: List[dict] = []
        if synth_txs is None:
            transfers, data_source = self._try_live(request)
            if transfers is not None:
                synth_txs = transfers
                wallet_rows = self._to_wallet_rows(transfers)
            else:
                data_source = "demo"
                from graph.synthetic import generate_transactions

                synth_txs = generate_transactions(seed=42, count=30)

        graph = self._transfers_to_graph(synth_txs, address)

        graph_data = self._graph_to_graph_data(graph, address, chain)

        intel = self._intel.lookup_address(address, chain, data_source=data_source)

        attr_request = AttributionRequest(
            address=address,
            chain=chain,
            graph_data=graph_data,
        )
        attr_response = self._attr.analyze(attr_request, data_source=data_source)

        evidence_count = 0
        for c in attr_response.candidates:
            evidence_count += len(c.evidence_ids)

        # Persist LIVE flow only; demo/synthetic data must never enter the
        # durable wallet store (it would be indistinguishable from real chain data).
        if data_source == "live":
            self._wallets.register_analysis(
                address=address,
                chain=chain,
                transfers=wallet_rows,
            )
            if self._sync_to_neo4j:
                self._sync_live_to_neo4j(wallet_rows)

        return InvestigationResult(
            address=address,
            chain=chain,
            data_source=data_source,
            transfers_ingested=len(synth_txs),
            graph_nodes=graph.node_count,
            graph_edges=graph.edge_count,
            address_intelligence=intel,
            candidates=attr_response.candidates,
            analysis_id=attr_response.analysis_id,
            evidence_count=evidence_count,
            transactions=wallet_rows,
        )