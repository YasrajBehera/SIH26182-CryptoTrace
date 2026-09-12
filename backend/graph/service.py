from typing import Callable, Dict, Iterable, List, Optional

from neo4j import Driver

from app.db import SessionLocal, ensure_database_tables
from app.models import Transaction
from graph.builder import TransactionGraph, amount_weight, hop_weight
from graph.neo4j_client import is_neo4j_healthy, neo4j_session
from graph.projection import CLUSTER_GRAPH, TX_FLOW_GRAPH, project_cluster_graph, project_tx_flow
from graph.schema import address_key, transaction_key
from graph import temporal

MERGE_TRANSACTION = """
MERGE (tx:Transaction {tx_id: $tx_id})
ON CREATE SET
  tx.tx_hash = $tx_hash,
  tx.chain = $chain,
  tx.block_number = $block_number,
  tx.block_timestamp = $block_timestamp,
  tx.value = $value
ON MATCH SET
  tx.tx_hash = $tx_hash,
  tx.chain = $chain,
  tx.block_number = $block_number,
  tx.block_timestamp = $block_timestamp,
  tx.value = $value
WITH tx
MERGE (src:Wallet {wallet_id: $src_wid})
SET src.address = $from_address, src.chain = $chain
MERGE (dst:Wallet {wallet_id: $dst_wid})
SET dst.address = $to_address, dst.chain = $chain
WITH tx, src, dst
MERGE (src)-[s:SENT {tx_id: $tx_id}]->(tx)
SET s.amount = $value, s.timestamp = $block_timestamp, s.chain = $chain
MERGE (tx)-[r:RECEIVED {tx_id: $tx_id}]->(dst)
SET r.amount = $value, r.timestamp = $block_timestamp, r.chain = $chain
"""

# Neo4j 5 forbids bound parameters inside variable-length relationship patterns
# (e.g. ``[*1..$max_depth]``). The depth is therefore injected as a *validated*
# integer literal; ``wallet_id`` and ``max_nodes`` stay bound parameters.
MAX_BFS_DEPTH = 50

BFS_QUERY_TEMPLATE = """
MATCH (start:Wallet {{wallet_id: $wallet_id}})
MATCH path = (start)-[*1..{max_depth}]-(other:Wallet)
WHERE other <> start
RETURN other.wallet_id AS wallet_id,
       other.address AS address,
       other.chain AS chain,
       min(length(path)) AS depth
ORDER BY depth, wallet_id
LIMIT $max_nodes
"""


def _validate_depth(max_depth: int, *, max_allowed: int = MAX_BFS_DEPTH) -> int:
    """Coerce and bound max_depth before it is embedded in a Cypher query.

    Inlining a raw value into the variable-length pattern would be a Cypher
    injection vector, so only a validated, bounded integer is ever formatted
    into ``BFS_QUERY_TEMPLATE``.
    """
    try:
        depth = int(max_depth)
    except (TypeError, ValueError):
        raise ValueError(f"max_depth must be an integer, got {max_depth!r}") from None
    if depth < 1:
        raise ValueError(f"max_depth must be >= 1, got {depth}")
    if depth > max_allowed:
        raise ValueError(f"max_depth must be <= {max_allowed}, got {depth}")
    return depth

DFS_QUERY = """
MATCH (start:Wallet {wallet_id: $wallet_id})
CALL apoc.path.expand(start, null, 'Wallet', 1, $max_depth, {limit: $max_nodes, bfs: false})
YIELD path
WITH nodes(path) AS path_nodes
UNWIND path_nodes AS node
WITH node
WHERE node:Wallet
RETURN DISTINCT node.wallet_id AS wallet_id,
                node.address AS address,
                node.chain AS chain
LIMIT $max_nodes
"""

SHORTEST_PATH_QUERY = """
CALL gds.shortestPath.dijkstra.stream($graph, {
  sourceNode: $source_id,
  targetNode: $target_id,
  relationshipWeightProperty: $weight
})
YIELD nodeIds, totalCost
WITH nodeIds, totalCost
UNWIND nodeIds AS node_id
WITH collect({
  node_id: node_id,
  label: labels(gds.util.asNode(node_id))[0],
  wallet_id: gds.util.asNode(node_id).wallet_id,
  tx_id: gds.util.asNode(node_id).tx_id,
  address: gds.util.asNode(node_id).address
}) AS nodes, totalCost
RETURN nodes, totalCost
"""

COUNT_WALLETS = "MATCH (w:Wallet) RETURN count(w) AS count"
COUNT_TRANSACTIONS = "MATCH (t:Transaction) RETURN count(t) AS count"

TEMPLATE_OUT_FLOW = """
MATCH (wallet:Wallet {wallet_id: $wallet_id})
MATCH (wallet)-[s:SENT]->(tx:Transaction)<-[r:RECEIVED]-(counterparty:Wallet)
WHERE counterparty.wallet_id <> $wallet_id {where_clause}
RETURN wallet.wallet_id AS source,
       tx.tx_id AS tx_id,
       tx.tx_hash AS tx_hash,
       tx.chain AS chain,
       tx.block_timestamp AS block_timestamp,
       s.amount AS amount,
       counterparty.wallet_id AS target
LIMIT $max_results
"""

TEMPLATE_IN_FLOW = """
MATCH (wallet:Wallet {wallet_id: $wallet_id})
MATCH (counterparty:Wallet)-[s:SENT]->(tx:Transaction)<-[r:RECEIVED]-(wallet)
WHERE counterparty.wallet_id <> $wallet_id {where_clause}
RETURN counterparty.wallet_id AS source,
       tx.tx_id AS tx_id,
       tx.tx_hash AS tx_hash,
       tx.chain AS chain,
       tx.block_timestamp AS block_timestamp,
       s.amount AS amount,
       wallet.wallet_id AS target
LIMIT $max_results
"""

CLUSTER_QUERY = """
CALL {procedure}($graph, {{}})
YIELD nodeId, communityId
WITH communityId, gds.util.asNode(nodeId) AS node
WHERE node:Wallet
RETURN communityId AS community_id,
       collect({{wallet_id: node.wallet_id, address: node.address, chain: node.chain}}) AS wallets
"""

CLUSTER_PROCEDURES = {
    "wcc": "gds.wcc.stream",
    "louvain": "gds.louvain.stream",
    "leiden": "gds.leiden.stream",
}


def normalize_wallet_id(wallet_id: str) -> str:
    """Canonicalize a wallet_id to lowercase chain:address.

    All writers store ``chain:address`` via ``graph.schema.address_key`` (which
    lowercases the address), but route parameters may arrive uppercase.
    """
    if ":" in wallet_id:
        chain, address = wallet_id.split(":", 1)
        return f"{chain.lower()}:{address.lower()}"
    return wallet_id


def sync_from_postgres(
    driver: Driver,
    db_session_factory: Callable = SessionLocal,
    batch_size: int = 1000,
) -> Dict:
    ensure_database_tables()
    synced = 0
    with db_session_factory() as db:
        transactions: Iterable[Transaction] = (
            db.query(Transaction).order_by(Transaction.id).yield_per(batch_size)
        )
        with neo4j_session(driver) as graph:
            for tx in transactions:
                timestamp = int(tx.block_timestamp.timestamp()) if tx.block_timestamp else 0
                params = {
                    "tx_id": transaction_key(tx.chain, tx.tx_hash),
                    "tx_hash": tx.tx_hash,
                    "chain": tx.chain,
                    "block_number": tx.block_number,
                    "block_timestamp": timestamp,
                    "value": str(tx.value),
                    "src_wid": address_key(tx.chain, tx.from_address),
                    "dst_wid": address_key(tx.chain, tx.to_address),
                    "from_address": tx.from_address,
                    "to_address": tx.to_address,
                }
                graph.run(MERGE_TRANSACTION, **params)
                synced += 1
    return {"synced": synced}


def build_graph(
    driver: Driver,
    db_session_factory: Callable = SessionLocal,
) -> Dict:
    graph = TransactionGraph.build(db_session_factory=db_session_factory)
    return {
        "wallet_count": graph.node_count,
        "transaction_count": graph.edge_count,
    }


def graph_health(driver: Driver) -> Dict:
    if not is_neo4j_healthy(driver):
        return {"status": "unavailable", "wallets": 0, "transactions": 0}
    with neo4j_session(driver) as session:
        wallets = session.run(COUNT_WALLETS).single()["count"]
        transactions = session.run(COUNT_TRANSACTIONS).single()["count"]
    return {"status": "ok", "wallets": wallets, "transactions": transactions}


def bfs(
    driver: Driver,
    wallet_id: str,
    max_depth: int = 3,
    max_nodes: int = 100,
) -> List[Dict]:
    query = BFS_QUERY_TEMPLATE.format(max_depth=_validate_depth(max_depth))
    with neo4j_session(driver) as session:
        records = session.run(
            query,
            wallet_id=normalize_wallet_id(wallet_id),
            max_nodes=int(max_nodes),
        )
        return [dict(record) for record in records]


def neighbors(
    driver: Driver,
    wallet_id: str,
    depth: int = 1,
    max_nodes: int = 100,
) -> List[Dict]:
    return bfs(driver, wallet_id, max_depth=depth, max_nodes=max_nodes)


def bfs_shortest_path(
    driver: Driver,
    source: str,
    target: str,
    db_session_factory: Callable = SessionLocal,
) -> Dict:
    graph = TransactionGraph.build(db_session_factory=db_session_factory)
    return graph.bfs_path(source, target)


def dfs_path(
    driver: Driver,
    source: str,
    target: str,
    db_session_factory: Callable = SessionLocal,
) -> Dict:
    graph = TransactionGraph.build(db_session_factory=db_session_factory)
    return graph.dfs_path(source, target)


def shortest_path_by_hops(
    driver: Driver,
    source: str,
    target: str,
    db_session_factory: Callable = SessionLocal,
) -> Dict:
    graph = TransactionGraph.build(db_session_factory=db_session_factory)
    return graph.shortest_path(source, target)


WEIGHT_FUNCTIONS = {
    "hops": hop_weight,
    "amount": amount_weight,
}


def weighted_path(
    driver: Driver,
    source: str,
    target: str,
    weight: str = "hops",
    db_session_factory: Callable = SessionLocal,
) -> Dict:
    if weight not in WEIGHT_FUNCTIONS:
        raise ValueError(
            f"Unknown weight {weight!r}; choose from {sorted(WEIGHT_FUNCTIONS)}"
        )
    graph = TransactionGraph.build(db_session_factory=db_session_factory)
    return graph.weighted_path(source, target, weight_fn=WEIGHT_FUNCTIONS[weight])


def temporal_path_analysis(
    driver: Driver,
    source: str,
    target: str,
    db_session_factory: Callable = SessionLocal,
) -> Dict:
    graph = TransactionGraph.build(db_session_factory=db_session_factory)
    return temporal.temporal_path(graph, source, target)


def fund_flow_analysis(
    driver: Driver,
    source: str,
    target: str,
    db_session_factory: Callable = SessionLocal,
) -> Dict:
    graph = TransactionGraph.build(db_session_factory=db_session_factory)
    return temporal.fund_flow(graph, source, target)


def dfs(
    driver: Driver,
    wallet_id: str,
    max_depth: int = 6,
    max_nodes: int = 100,
) -> List[Dict]:
    with neo4j_session(driver) as session:
        records = session.run(
            DFS_QUERY,
            wallet_id=normalize_wallet_id(wallet_id),
            max_depth=int(max_depth),
            max_nodes=int(max_nodes),
        )
        return [dict(record) for record in records]


def shortest_path(
    driver: Driver,
    source: str,
    target: str,
    weight: str = "hops",
) -> Dict:
    project_tx_flow(driver)
    with neo4j_session(driver) as session:
        source_id = session.run(
            "MATCH (w:Wallet {wallet_id: $wallet_id}) RETURN id(w) AS id",
            wallet_id=source,
        ).single()
        target_id = session.run(
            "MATCH (w:Wallet {wallet_id: $wallet_id}) RETURN id(w) AS id",
            wallet_id=target,
        ).single()
        if not source_id or not target_id:
            return {
                "source": source,
                "target": target,
                "weight": weight,
                "found": False,
                "total_cost": None,
                "nodes": [],
            }
        weight_arg = None if weight == "hops" else "amount"
        record = session.run(
            SHORTEST_PATH_QUERY,
            graph=TX_FLOW_GRAPH,
            source_id=source_id["id"],
            target_id=target_id["id"],
            weight=weight_arg,
        ).single()
        if not record:
            return {
                "source": source,
                "target": target,
                "weight": weight,
                "found": False,
                "total_cost": None,
                "nodes": [],
            }
        return {
            "source": source,
            "target": target,
            "weight": weight,
            "found": True,
            "total_cost": record["totalCost"],
            "nodes": [dict(node) for node in record["nodes"]],
        }


def temporal_flow(
    driver: Driver,
    wallet_id: str,
    from_ts: Optional[int] = None,
    to_ts: Optional[int] = None,
    direction: str = "all",
    max_results: int = 500,
) -> List[Dict]:
    conditions = []
    if from_ts is not None:
        conditions.append("tx.block_timestamp >= $from_ts")
    if to_ts is not None:
        conditions.append("tx.block_timestamp <= $to_ts")
    where_clause = "AND " + " AND ".join(conditions) if conditions else ""

    templates = []
    if direction in ("out", "all"):
        templates.append(TEMPLATE_OUT_FLOW)
    if direction in ("in", "all"):
        templates.append(TEMPLATE_IN_FLOW)

    with neo4j_session(driver) as session:
        rows: List[Dict] = []
        for template in templates:
            query = template.replace("{where_clause}", where_clause)
            records = session.run(
                query,
                wallet_id=normalize_wallet_id(wallet_id),
                from_ts=from_ts,
                to_ts=to_ts,
                max_results=int(max_results),
            )
            rows.extend(dict(record) for record in records)
    return rows


def clusters(
    driver: Driver,
    algorithm: str = "louvain",
    min_community_size: int = 2,
) -> List[Dict]:
    if algorithm not in CLUSTER_PROCEDURES:
        raise ValueError(
            f"Unknown algorithm {algorithm!r}; choose from {sorted(CLUSTER_PROCEDURES)}"
        )
    project_cluster_graph(driver)
    with neo4j_session(driver) as session:
        query = CLUSTER_QUERY.format(procedure=CLUSTER_PROCEDURES[algorithm])
        records = session.run(query, graph=CLUSTER_GRAPH)
        communities = [dict(record) for record in records]

    groups = [
        {"community_id": item["community_id"], "wallets": item["wallets"]}
        for item in communities
        if len(item["wallets"]) >= min_community_size
    ]
    return sorted(groups, key=lambda item: len(item["wallets"]), reverse=True)