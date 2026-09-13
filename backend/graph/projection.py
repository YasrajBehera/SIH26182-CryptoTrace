from typing import Dict

from neo4j import Driver

from graph.neo4j_client import neo4j_session
from graph.schema import RECEIVED_REL, SENT_REL, TRANSACTION_LABEL, WALLET_LABEL

TX_FLOW_GRAPH = "txflow"
CLUSTER_GRAPH = "txclusters"

NODE_SPEC: Dict = {
    WALLET_LABEL: {},
    TRANSACTION_LABEL: {},
}


def _relationship_spec(orientation: str) -> Dict:
    # GDS only ingests numeric relationship properties (TEXT amount strings
    # used for display would abort the projection), so we project the numeric
    # ``amount_value`` alongside ``timestamp``.
    return {
        SENT_REL: {
            "type": SENT_REL,
            "orientation": orientation,
            "properties": ["amount_value", "timestamp"],
        },
        RECEIVED_REL: {
            "type": RECEIVED_REL,
            "orientation": orientation,
            "properties": ["amount_value", "timestamp"],
        },
    }


def _graph_exists(session, graph_name: str) -> bool:
    record = session.run(
        "CALL gds.graph.exists($name) YIELD exists",
        name=graph_name,
    ).single()
    return bool(record and record["exists"])


def project_tx_flow(driver: Driver) -> None:
    with neo4j_session(driver) as session:
        if _graph_exists(session, TX_FLOW_GRAPH):
            return
        session.run(
            "CALL gds.graph.project($name, $nodes, $relationships)",
            name=TX_FLOW_GRAPH,
            nodes=NODE_SPEC,
            relationships=_relationship_spec("NATURAL"),
        )


def project_cluster_graph(driver: Driver) -> None:
    with neo4j_session(driver) as session:
        if _graph_exists(session, CLUSTER_GRAPH):
            return
        session.run(
            "CALL gds.graph.project($name, $nodes, $relationships)",
            name=CLUSTER_GRAPH,
            nodes=NODE_SPEC,
            relationships=_relationship_spec("UNDIRECTED"),
        )


def drop_projection(driver: Driver, graph_name: str) -> None:
    with neo4j_session(driver) as session:
        session.run(
            "CALL gds.graph.drop($name, false)",
            name=graph_name,
        )