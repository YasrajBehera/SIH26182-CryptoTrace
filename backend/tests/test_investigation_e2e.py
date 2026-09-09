"""End-to-end synthetic investigation test for the CryptoTrace graph module.

The flow under investigation is fully synthetic:

    Suspicious_Wallet -> Wallet_A -> Wallet_B -> Wallet_C -> VASP_X

A longer alternate branch (Suspicious_Wallet -> Wallet_P -> Wallet_Q ->
Wallet_R -> Wallet_S -> VASP_X) exists so that shortest-path and
weighted-path analysis return different, individually testable results.

NOTE: "VASP_X" is a synthetic placeholder label for a fabricated wallet
address. It is NOT a real VASP and no real-world attribution is implied.
"""

from datetime import datetime, timezone
from decimal import Decimal

from graph import temporal
from graph.builder import TransactionGraph, amount_weight

CHAIN = "eth"
T0 = 1704067200


def _addr(digit: str) -> str:
    return "0x" + digit * 40


WALLETS = {
    "Suspicious_Wallet": _addr("1"),
    "Wallet_A": _addr("2"),
    "Wallet_B": _addr("3"),
    "Wallet_C": _addr("4"),
    "VASP_X": _addr("5"),
    "Wallet_P": _addr("6"),
    "Wallet_Q": _addr("7"),
    "Wallet_R": _addr("8"),
    "Wallet_S": _addr("9"),
}

WALLET_IDS = {label: f"{CHAIN}:{addr}" for label, addr in WALLETS.items()}

MAIN_PATH = [
    WALLET_IDS["Suspicious_Wallet"],
    WALLET_IDS["Wallet_A"],
    WALLET_IDS["Wallet_B"],
    WALLET_IDS["Wallet_C"],
    WALLET_IDS["VASP_X"],
]

ALTERNATE_PATH = [
    WALLET_IDS["Suspicious_Wallet"],
    WALLET_IDS["Wallet_P"],
    WALLET_IDS["Wallet_Q"],
    WALLET_IDS["Wallet_R"],
    WALLET_IDS["Wallet_S"],
    WALLET_IDS["VASP_X"],
]


def _hash_ref(index: int) -> str:
    return f"0x{index:064x}"


def edge_row(index, sender_addr, receiver_addr, ts_offset, amount):
    return {
        "chain": CHAIN,
        "tx_hash": _hash_ref(index),
        "block_timestamp": datetime.fromtimestamp(T0 + ts_offset, tz=timezone.utc),
        "from_address": sender_addr,
        "to_address": receiver_addr,
        "value": Decimal(str(amount)),
    }


def build_flow_graph() -> TransactionGraph:
    w = WALLETS
    rows = [
        edge_row(1, w["Suspicious_Wallet"], w["Wallet_A"], 100, 100),
        edge_row(2, w["Suspicious_Wallet"], w["Wallet_A"], 200, 150),
        edge_row(3, w["Wallet_A"], w["Wallet_B"], 300, 100),
        edge_row(4, w["Wallet_B"], w["Wallet_C"], 400, 100),
        edge_row(5, w["Wallet_C"], w["VASP_X"], 500, 100),
        edge_row(6, w["Suspicious_Wallet"], w["Wallet_P"], 600, 1),
        edge_row(7, w["Wallet_P"], w["Wallet_Q"], 700, 1),
        edge_row(8, w["Wallet_Q"], w["Wallet_R"], 800, 1),
        edge_row(9, w["Wallet_R"], w["Wallet_S"], 900, 1),
        edge_row(10, w["Wallet_S"], w["VASP_X"], 1000, 1),
    ]
    return TransactionGraph.from_transactions(rows)


def investigate(graph: TransactionGraph, source: str, target: str) -> dict:
    return {
        "source": source,
        "destination": target,
        "summary": {
            "wallet_count": graph.node_count,
            "transaction_count": graph.edge_count,
        },
        "bfs": graph.bfs_path(source, target),
        "dfs": graph.dfs_path(source, target),
        "shortest_path": graph.shortest_path(source, target),
        "weighted_path": graph.weighted_path(source, target, weight_fn=amount_weight),
        "temporal": temporal.temporal_path(graph, source, target),
        "fund_flow": temporal.fund_flow(graph, source, target),
    }


def test_end_to_end_synthetic_investigation():
    graph = build_flow_graph()
    source = WALLET_IDS["Suspicious_Wallet"]
    destination = WALLET_IDS["VASP_X"]
    result = investigate(graph, source, destination)

    assert result["source"] == source
    assert result["destination"] == destination
    assert set(result) == {
        "source",
        "destination",
        "summary",
        "bfs",
        "dfs",
        "shortest_path",
        "weighted_path",
        "temporal",
        "fund_flow",
    }

    assert result["summary"] == {"wallet_count": 9, "transaction_count": 10}

    bfs = result["bfs"]
    assert bfs["found"] is True
    assert bfs["hop_count"] == 4
    assert bfs["path"] == MAIN_PATH

    dfs = result["dfs"]
    assert dfs["found"] is True
    assert dfs["path"][0] == source
    assert dfs["path"][-1] == destination
    assert dfs["hop_count"] == len(dfs["path"]) - 1

    shortest = result["shortest_path"]
    assert shortest["path_exists"] is True
    assert shortest["hop_count"] == 4
    assert shortest["path"] == MAIN_PATH

    weighted = result["weighted_path"]
    assert weighted["path_exists"] is True
    assert weighted["total_cost"] == 5.0
    assert weighted["hop_count"] == 5
    assert weighted["path"] == ALTERNATE_PATH

    temporal_result = result["temporal"]
    assert temporal_result["found"] is True
    assert temporal_result["total_hops"] == 4
    assert temporal_result["path"] == MAIN_PATH
    assert [edge["tx_hash"] for edge in temporal_result["edges"]] == [
        _hash_ref(1),
        _hash_ref(3),
        _hash_ref(4),
        _hash_ref(5),
    ]
    assert [edge["timestamp"] - T0 for edge in temporal_result["edges"]] == [
        100, 300, 400, 500,
    ]
    assert temporal_result["is_temporally_valid"] is True

    flow = result["fund_flow"]
    assert flow["found"] is True
    assert flow["hop_count"] == 4
    assert flow["wallet_path"] == MAIN_PATH
    assert [tx["tx_hash"] for tx in flow["transactions"]] == [
        _hash_ref(i) for i in (1, 2, 3, 4, 5)
    ]
    assert [tx["timestamp"] - T0 for tx in flow["transactions"]] == [
        100, 200, 300, 400, 500,
    ]
    assert [tx["amount"] for tx in flow["transactions"]] == [
        "100", "150", "100", "100", "100",
    ]
    for tx in flow["transactions"]:
        assert isinstance(tx["timestamp"], int)
        assert isinstance(tx["amount"], str)


def test_shortest_uses_fewest_hops_and_weighted_uses_cheapest_amount():
    graph = build_flow_graph()
    source = WALLET_IDS["Suspicious_Wallet"]
    destination = WALLET_IDS["VASP_X"]

    hop_shortest = graph.shortest_path(source, destination)
    amount_cheapest = graph.weighted_path(
        source, destination, weight_fn=amount_weight
    )

    assert hop_shortest["path"] == MAIN_PATH
    assert hop_shortest["hop_count"] == 4
    assert amount_cheapest["path"] == ALTERNATE_PATH
    assert amount_cheapest["hop_count"] == 5
    assert amount_cheapest["total_cost"] == 5.0
    assert hop_shortest["path"] != amount_cheapest["path"]


def test_fund_flow_collects_all_transactions_for_pairs():
    graph = build_flow_graph()
    source = WALLET_IDS["Suspicious_Wallet"]
    destination = WALLET_IDS["VASP_X"]

    flow = temporal.fund_flow(graph, source, destination)

    assert [tx["tx_hash"] for tx in flow["transactions"]] == [
        _hash_ref(i) for i in (1, 2, 3, 4, 5)
    ]
    assert [tx["amount"] for tx in flow["transactions"]] == [
        "100", "150", "100", "100", "100",
    ]