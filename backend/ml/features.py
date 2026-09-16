"""Live feature extraction from REAL blockchain data.

Only ever consumes normalized on-chain transfers (the same rows the wallet
store persists from the Alchemy pipeline). It computes the canonical
interpretable features from ``ml.schema`` and NEVER imputes: a feature whose
underlying statistic is undefined for the available data is marked missing,
which downstream forces an UNKNOWN / NOT ASSESSED prediction instead of a
fabricated one.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import fmean, median, pstdev
from typing import Dict, Iterable, List, Optional, Tuple

from ml.curated_illicit import (
    load_curated_illicit_addresses,
    load_curated_mixers,
)
from ml.schema import (
    CANONICAL_FEATURES,
    GRAPH_FEATURES,
    RISK_FEATURES,
    TEMPORAL_FEATURES,
    VOLUME_FEATURES,
)


class FeatureVector:
    """One wallet's feature vector plus an explicit missing-feature set.

    ``values`` holds only features that were actually computed from real data.
    ``missing`` holds every canonical feature that could NOT be computed — a
    prediction that needs any of them is UNKNOWN, never approximated.
    """

    def __init__(self, values: Dict[str, float], missing: set) -> None:
        for name in values:
            if name not in CANONICAL_FEATURES:
                raise ValueError(f"Unknown feature '{name}' in live vector")
        self._values = dict(values)
        self._missing = set(missing)

    @property
    def missing(self) -> set:
        return set(self._missing)

    @property
    def missing_names(self) -> List[str]:
        return sorted(self._missing)

    def is_available(self, name: str) -> bool:
        return name in CANONICAL_FEATURES and name not in self._missing

    def value(self, name: str) -> Optional[float]:
        if name in self._missing:
            return None
        return self._values.get(name)

    def as_array(self, features: Iterable[str]) -> Optional[List[float]]:
        """Row for the model, or None when any required feature is missing."""
        features = list(features)
        if any(f in self._missing for f in features):
            return None
        return [self._values.get(f, 0.0) for f in features]

    def feature_names(self) -> List[str]:
        return CANONICAL_FEATURES


def _transfer_row(item) -> dict:
    """Normalize one transfer into {from, to, value, ts} regardless of whether
    it is a dict, a DB row dict, or a pydantic BlockchainTransfer."""
    if hasattr(item, "model_dump"):
        item = item.model_dump()
    if not isinstance(item, dict):
        raise TypeError(f"Unsupported transfer item: {type(item).__name__}")
    row = {}
    row["from"] = str(item.get("from_address") or "").lower()
    row["to"] = str(item.get("to_address") or "").lower()
    raw_value = item.get("value")
    if raw_value is None:
        raw_value = item.get("raw_contract_value")
    row["has_value"] = raw_value is not None and str(raw_value) not in ("", "None")
    try:
        if row["has_value"]:
            row["value"] = float(str(raw_value))
    except (TypeError, ValueError):
        row["has_value"] = False
    ts = item.get("block_timestamp")
    row["ts"] = _to_epoch_seconds(ts)
    row["has_ts"] = row["ts"] is not None
    return row


def _to_epoch_seconds(ts) -> Optional[float]:
    if ts is None:
        return None
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.timestamp()
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, str):
        ts = ts.strip()
        if not ts:
            return None
        try:
            return float(ts)
        except ValueError:
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
            except ValueError:
                return None
    return None


def _pagerank_ego(adj_in: Dict[str, set], adj_out: Dict[str, set], target: str) -> Optional[float]:
    nodes = set(adj_in) | set(adj_out)
    if len(nodes) < 2:
        return None
    damping = 0.85
    iters = 50
    n = len(nodes)
    ranks = {node: 1.0 / n for node in nodes}
    for _ in range(iters):
        new_ranks = {}
        for node in nodes:
            incoming = adj_in.get(node) or set()
            contrib = 0.0
            for src in incoming:
                degree = len(adj_out.get(src) or set())
                if degree > 0:
                    contrib += ranks[src] / degree
            new_ranks[node] = (1.0 - damping) / n + damping * contrib
        delta = sum(abs(new_ranks[n] - ranks[n]) for n in nodes)
        ranks = new_ranks
        if delta < 1e-9:
            break
    return ranks.get(target)


class LiveFeatureExtractor:
    """Computes the canonical interpretable features from real transfers."""

    def __init__(self) -> None:
        self._illicit = load_curated_illicit_addresses()
        self._mixers = load_curated_mixers()

    def compute(self, address: str, chain: str = "eth", transfers=None) -> FeatureVector:
        target = str(address).lower()
        chain = str(chain).lower()
        rows = [_transfer_row(t) for t in (transfers or [])
                if _row_belongs(_transfer_row(t), target)]

        values: Dict[str, float] = {}
        missing = set()

        # ---- counts ----------------------------------------------------- #
        in_edges = [r for r in rows if r["to"] == target]
        out_edges = [r for r in rows if r["from"] == target]
        values["tx_count"] = float(len(rows))
        values["incoming_count"] = float(len(in_edges))
        values["outgoing_count"] = float(len(out_edges))

        # ---- counterparties --------------------------------------------- #
        incoming_cps = {r["from"] for r in in_edges if r["from"] not in ("", target)}
        outgoing_cps = {r["to"] for r in out_edges if r["to"] not in ("", target)}
        all_cps = incoming_cps | outgoing_cps
        values["unique_counterparties"] = float(len(all_cps))
        values["unique_incoming_counterparties"] = float(len(incoming_cps))
        values["unique_outgoing_counterparties"] = float(len(outgoing_cps))

        # ---- volumes / value statistics --------------------------------- #
        has_all_values = all(r["has_value"] for r in rows)
        volumes_available = has_all_values and len(rows) > 0
        in_values = [r["value"] for r in in_edges if r.get("has_value")]
        out_values = [r["value"] for r in out_edges if r.get("has_value")]

        if volumes_available:
            values["incoming_volume"] = sum(in_values)
            values["outgoing_volume"] = sum(out_values)
            values["total_volume"] = sum(in_values) + sum(out_values)
            values["avg_value"] = fmean(in_values + out_values)
            values["median_value"] = median(in_values + out_values)
            values["max_value"] = max(in_values + out_values)
            values["std_value"] = pstdev(in_values + out_values) if len(in_values + out_values) > 1 else 0.0
        else:
            missing |= VOLUME_FEATURES

        # ---- temporal --------------------------------------------------- #
        ts = [r["ts"] for r in rows if r.get("has_ts")]
        all_ts_present = all(r.get("has_ts") for r in rows)
        if not volumes_available or not all_ts_present or len(ts) < 2:
            missing |= TEMPORAL_FEATURES
        else:
            ts_sorted = sorted(ts)
            span_seconds = ts_sorted[-1] - ts_sorted[0]
            duration_days = span_seconds / 86400.0
            days = Counter(datetime.fromtimestamp(t, tz=timezone.utc).date() for t in ts_sorted)
            day_counts = list(days.values())
            gaps = [b - a for a, b in zip(ts_sorted, ts_sorted[1:])]
            gap_mean = fmean(gaps)
            if span_seconds <= 0 or gap_mean <= 0:
                missing |= TEMPORAL_FEATURES
            else:
                values["tx_per_day_frequency"] = len(ts_sorted) / duration_days
                values["inter_arrival_mean_seconds"] = gap_mean
                values["inter_arrival_cv"] = (
                    pstdev(gaps) / gap_mean if len(gaps) > 1 else 0.0
                )
                values["active_duration_days"] = duration_days
                values["active_days"] = float(len(day_counts))
                values["max_txs_in_single_day"] = float(max(day_counts))
                values["active_day_ratio"] = float(len(day_counts)) / duration_days

        # ---- graph ------------------------------------------------------ #
        nodes = set(all_cps) | {target}
        if len(nodes) < 2:
            missing |= GRAPH_FEATURES
        else:
            adj_out: Dict[str, set] = defaultdict(set)
            adj_in: Dict[str, set] = defaultdict(set)
            for r in rows:
                a, b = r["from"], r["to"]
                if a and b:
                    adj_out[a].add(b)
                    adj_in[b].add(a)
            values["degree"] = float(len(all_cps))
            values["in_degree"] = float(len(incoming_cps))
            values["out_degree"] = float(len(outgoing_cps))
            if volumes_available:
                weighted = sum(r["value"] for r in rows if r["from"] == target or r["to"] == target)
                values["weighted_degree"] = weighted
            else:
                missing.add("weighted_degree")
            pr = _pagerank_ego(dict(adj_in), dict(adj_out), target)
            if pr is None:
                missing.add("ego_pagerank")
            else:
                values["ego_pagerank"] = pr
            clustering = _avg_clustering(nodes, adj_out)
            if clustering is None:
                missing.add("clustering_coefficient")
            else:
                values["clustering_coefficient"] = clustering
            recip = _reciprocity(rows)
            if recip is None:
                missing.add("reciprocity_ratio")
            else:
                values["reciprocity_ratio"] = recip

        # ---- risk / intelligence ---------------------------------------- #
        illicit_entries: List[Tuple[str, str]] = []
        mixer_entries: List[Tuple[str, str]] = []
        for cp in all_cps:
            if (chain, cp) in self._illicit:
                illicit_entries.append(("illicit", cp))
            if (chain, cp) in self._mixers:
                mixer_entries.append(("mixer", cp))
        illicit_cps = {cp for _, cp in illicit_entries}
        mixer_cps = {cp for _, cp in mixer_entries}

        values["sanctions_exact_match"] = 1.0 if (chain, target) in self._illicit else 0.0
        values["illicit_counterparty_exposure"] = (
            len(illicit_cps) / len(all_cps) if all_cps else 0.0
        )
        values["mixer_exposure"] = len(mixer_cps) / len(all_cps) if all_cps else 0.0
        if volumes_available and len(rows) > 0:
            illicit_volume = sum(
                r["value"] for r in rows
                if (r["from"] in illicit_cps or r["to"] in illicit_cps)
            )
            total = sum(r["value"] for r in rows)
            values["illicit_exposure_volume_ratio"] = illicit_volume / total if total else 0.0
        else:
            missing.add("illicit_exposure_volume_ratio")

        for name in set(CANONICAL_FEATURES):
            if name in values:
                values[name] = float(values[name])
        missing = {name for name in CANONICAL_FEATURES if name not in values}
        return FeatureVector(values, missing)


def _row_belongs(row: dict, target: str) -> bool:
    return row["from"] == target or row["to"] == target


def _avg_clustering(nodes, adj_out: Dict[str, set]) -> Optional[float]:
    """Average local clustering coefficient over the ego graph (undirected)."""
    if len(nodes) < 3:
        return None
    neighbors: Dict[str, set] = defaultdict(set)
    for src, dsts in adj_out.items():
        for dst in dsts:
            neighbors[src].add(dst)
            neighbors[dst].add(src)
    scores = []
    for node in nodes:
        neighs = neighbors.get(node) or set()
        k = len(neighs)
        if k < 2:
            continue
        links = 0
        for a in neighs:
            for b in neighs:
                if a != b and b in (neighbors.get(a) or set()):
                    links += 1
        scores.append(links / (k * (k - 1)))
    if not scores:
        return 0.0
    return fmean(scores)


def _reciprocity(rows: List[dict]) -> Optional[float]:
    edges = {(r["from"], r["to"]) for r in rows if r["from"] and r["to"]}
    if not edges:
        return None
    reciprocal = sum(1 for (a, b) in edges if (b, a) in edges)
    return float(reciprocal) / float(len(edges))