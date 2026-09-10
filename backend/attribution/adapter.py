from typing import Any, Dict, List, Optional, Union


def _normalize_flow(flow: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure flow dict uses source/target naming for attribution scoring."""
    return {
        "tx_hash": flow.get("tx_hash", ""),
        "tx_id": flow.get("tx_id"),
        "chain": flow.get("chain", ""),
        "source": flow.get("source") or flow.get("sender", ""),
        "target": flow.get("target") or flow.get("receiver", ""),
        "amount": flow.get("amount", "0"),
        "timestamp": flow.get("timestamp") or flow.get("block_timestamp", 0),
    }


def build_graph_data(
    bfs: Optional[Dict] = None,
    path: Optional[Dict] = None,
    temporal_path: Optional[Dict] = None,
    fund_flow: Optional[Dict] = None,
    temporal_flow: Optional[Union[Dict, List]] = None,
    clusters: Optional[Dict] = None,
) -> Dict:
    """Transform Member 2 graph responses into attribution graph_data.

    Accepts any combination of Member 2 response dicts (in their native
    JSON-serialised form) and returns a unified dict suitable for
    ``AttributionRequest.graph_data``.

    Parameters correspond to Member 2 API responses:

    - bfs: BFSResponse from ``GET /graph/wallets/{id}/bfs`` or
      ``GET /graph/wallets/{id}/neighbors``
    - path: BFSPathResponse from ``GET /graph/bfs-path``
    - temporal_path: TemporalPathResponse from ``GET /graph/temporal-path``
    - fund_flow: FundFlowResponse from ``GET /graph/fund-flow``
    - temporal_flow: TemporalFlowResponse dict OR raw list of flow dicts
    - clusters: ClustersResponse from ``GET /graph/clusters``
    """
    result: Dict[str, Any] = {}

    if bfs:
        nodes = bfs.get("nodes", [])
        result["neighbors"] = [
            {"wallet_id": n.get("wallet_id", "")}
            for n in nodes
            if n.get("wallet_id")
        ]

    if path and (path.get("found") or path.get("path_exists")):
        result["path"] = {
            "found": True,
            "path": path.get("path", []),
            "hop_count": path.get("hop_count"),
        }

    if temporal_path and temporal_path.get("found"):
        result["path"] = {
            "found": True,
            "path": temporal_path.get("path", []),
            "hop_count": temporal_path.get("total_hops"),
        }
        edges = temporal_path.get("edges", [])
        if edges:
            result["edges"] = [_normalize_flow(e) for e in edges]

    if fund_flow and fund_flow.get("found"):
        transactions = fund_flow.get("transactions", [])
        if transactions:
            existing = result.get("flows", [])
            result["flows"] = existing + [_normalize_flow(t) for t in transactions]
        if not result.get("path") and fund_flow.get("wallet_path"):
            result["path"] = {
                "found": True,
                "path": fund_flow.get("wallet_path", []),
                "hop_count": fund_flow.get("hop_count"),
            }

    if temporal_flow is not None:
        if isinstance(temporal_flow, list):
            flows = temporal_flow
        elif isinstance(temporal_flow, dict):
            flows = temporal_flow.get("flows", [])
        else:
            flows = []
        if flows:
            existing = result.get("flows", [])
            result["flows"] = existing + [_normalize_flow(f) for f in flows]

    if clusters:
        result["communities"] = clusters.get("communities", [])

    return result
