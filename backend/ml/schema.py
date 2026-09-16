"""Canonical interpretable ML feature schema.

The suspicious-wallet classifier consumes ONE feature vector shape:

* the LIVE onset is computed by ``ml.features.LiveFeatureExtractor`` from real,
  normalized on-chain transfers (never synthetic data), and
* the TRAINING onset is computed by ``ml.dataset`` from a documented labeled
  dataset through the raw-column bridge.

Both sides speak the same named features below. A feature that cannot be
computed from the data available for a wallet is UNAVAILABLE — it is never
imputed, defaulted to a plausible value, or fabricated. A live prediction that
requires an unavailable feature is UNKNOWN / NOT ASSESSED.
"""

FEATURE_GROUPS = {
    "transaction": "Counts, volumes and value statistics of on-chain transfers.",
    "temporal": "Cadence and burstiness of activity over time.",
    "graph": "Ego-network topology (degree, centrality, clustering).",
    "risk_intelligence": "Known-illicit / mixer counterparty exposure and "
    "direct sanctions match from curated public intelligence.",
}

# Canonical feature names shared by the live extractor and the dataset bridge.
# Ordering is stable so a trained model's ``required_features`` list maps 1:1
# onto a live feature vector.
CANONICAL_FEATURES = [
    # --- transaction --------------------------------------------------- #
    "tx_count",
    "incoming_count",
    "outgoing_count",
    "incoming_volume",
    "outgoing_volume",
    "total_volume",
    "unique_counterparties",
    "unique_incoming_counterparties",
    "unique_outgoing_counterparties",
    "avg_value",
    "median_value",
    "max_value",
    "std_value",
    # --- temporal ------------------------------------------------------ #
    "tx_per_day_frequency",
    "inter_arrival_mean_seconds",
    "inter_arrival_cv",
    "active_duration_days",
    "active_days",
    "max_txs_in_single_day",
    "active_day_ratio",
    # --- graph --------------------------------------------------------- #
    "degree",
    "weighted_degree",
    "in_degree",
    "out_degree",
    "ego_pagerank",
    "clustering_coefficient",
    "reciprocity_ratio",
    # --- risk / intelligence ------------------------------------------ #
    "illicit_counterparty_exposure",
    "illicit_exposure_volume_ratio",
    "mixer_exposure",
    "sanctions_exact_match",
]

# Features whose underlying math is undefined for tiny/empty histories. These
# are the features that gate a live prediction toward UNKNOWN when a wallet has
# too little real data — by design (no plausible-value substitution).
VOLUME_FEATURES = {
    "incoming_volume",
    "outgoing_volume",
    "total_volume",
    "avg_value",
    "median_value",
    "max_value",
    "std_value",
}

TEMPORAL_FEATURES = {
    "tx_per_day_frequency",
    "inter_arrival_mean_seconds",
    "inter_arrival_cv",
    "active_duration_days",
    "active_days",
    "max_txs_in_single_day",
    "active_day_ratio",
}

GRAPH_FEATURES = {
    "degree",
    "weighted_degree",
    "in_degree",
    "out_degree",
    "ego_pagerank",
    "clustering_coefficient",
    "reciprocity_ratio",
}

RISK_FEATURES = {
    "illicit_counterparty_exposure",
    "illicit_exposure_volume_ratio",
    "mixer_exposure",
    "sanctions_exact_match",
}


def validate_feature_names(features):
    """Raise if any name is not a canonical feature (typo guard for the
    dataset bridge and trained-artifact metadata)."""
    allowed = set(CANONICAL_FEATURES)
    unknown = sorted(set(features) - allowed)
    if unknown:
        raise ValueError(
            "Unknown feature name(s) in feature schema: "
            f"{unknown}. Allowed: {sorted(allowed)}"
        )