from typing import Dict, List, Optional

from graph.builder import TransactionEdge


def sort_edges_by_time(
    edges: List[TransactionEdge], descending: bool = False
) -> List[TransactionEdge]:
    return sorted(edges, key=lambda e: e.timestamp, reverse=descending)


def _edge_between(graph, node_a: str, node_b: str) -> Optional[TransactionEdge]:
    candidates = [
        e for e in graph.get_edges_from(node_a) if e.receiver == node_b
    ] + [
        e for e in graph.get_edges_to(node_a) if e.sender == node_b
    ]
    return min(candidates, key=lambda e: e.timestamp) if candidates else None


def _all_edges_between(
    graph, node_a: str, node_b: str
) -> List[TransactionEdge]:
    candidates = [
        e for e in graph.get_edges_from(node_a) if e.receiver == node_b
    ] + [
        e for e in graph.get_edges_to(node_a) if e.sender == node_b
    ]
    return sort_edges_by_time(candidates)


def validate_temporal_sequence(edges: List[TransactionEdge]) -> Dict:
    if not edges:
        return {
            "is_valid": True,
            "temporal_valid": True,
            "chain_valid": True,
            "violations": [],
        }

    violations: List[Dict] = []
    temporal_valid = True
    chain_valid = True

    for i in range(len(edges) - 1):
        curr = edges[i]
        nxt = edges[i + 1]

        connected = (
            curr.receiver == nxt.sender
            or curr.receiver == nxt.receiver
            or curr.sender == nxt.sender
            or curr.sender == nxt.receiver
        )
        if not connected:
            chain_valid = False
            violations.append({
                "type": "chain_break",
                "index": i,
                "message": f"Edge {i} does not connect to edge {i + 1}",
            })

        if curr.timestamp > nxt.timestamp:
            temporal_valid = False
            violations.append({
                "type": "temporal_order",
                "index": i,
                "message": f"Timestamp {curr.timestamp} > {nxt.timestamp}",
            })

    return {
        "is_valid": temporal_valid and chain_valid,
        "temporal_valid": temporal_valid,
        "chain_valid": chain_valid,
        "violations": violations,
    }


def temporal_path(graph, source: str, target: str) -> Dict:
    result = graph.bfs_path(source, target)
    if not result["found"]:
        return {
            "source": source,
            "destination": target,
            "path": [],
            "edges": [],
            "is_temporally_valid": True,
            "total_hops": None,
            "found": False,
        }

    path = result["path"]
    edges: List[TransactionEdge] = []
    for i in range(len(path) - 1):
        edge = _edge_between(graph, path[i], path[i + 1])
        if edge is not None:
            edges.append(edge)

    validation = validate_temporal_sequence(edges)

    return {
        "source": source,
        "destination": target,
        "path": path,
        "edges": [
            {
                "tx_hash": e.tx_hash,
                "chain": e.chain,
                "sender": e.sender,
                "receiver": e.receiver,
                "amount": str(e.amount),
                "timestamp": e.timestamp,
            }
            for e in edges
        ],
        "is_temporally_valid": validation["is_valid"],
        "total_hops": result["hop_count"],
        "found": True,
    }


def fund_flow(graph, source: str, target: str) -> Dict:
    result = graph.bfs_path(source, target)
    if not result["found"]:
        return {
            "source": source,
            "destination": target,
            "wallet_path": [],
            "hop_count": None,
            "transactions": [],
            "found": False,
        }

    path = result["path"]
    transactions: List[TransactionEdge] = []
    for i in range(len(path) - 1):
        transactions.extend(_all_edges_between(graph, path[i], path[i + 1]))

    transactions = sort_edges_by_time(transactions)

    return {
        "source": source,
        "destination": target,
        "wallet_path": path,
        "hop_count": result["hop_count"],
        "transactions": [
            {
                "tx_hash": e.tx_hash,
                "chain": e.chain,
                "sender": e.sender,
                "receiver": e.receiver,
                "amount": str(e.amount),
                "timestamp": e.timestamp,
            }
            for e in transactions
        ],
        "found": True,
    }
