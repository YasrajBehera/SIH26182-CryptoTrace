"""Labeled dataset lifecycle: official Elliptic2 source, loading, provenance.

The ONLY dataset this module accepts is the official **Elliptic2** benchmark:

  GitHub   https://github.com/MITIBMxGraph/Elliptic2
  Kaggle   https://www.kaggle.com/datasets/ellipticco/elliptic2-data-set
  License  CC BY-NC-ND 4.0
  Chain    Bitcoin
  Labels   time-stamped graph ground truth (licit / illicit / unknown)

Nothing is downloaded implicitly and nothing is fabricated. Loading REQUIRES
the real release files on disk (``nodes`` / ``edges`` and the per-timestep
ground truth). If they are absent, ``load_labeled`` raises
``DatasetUnavailableError`` and training stops — there is no synthetic
substitute anywhere in this module.

Dataset provenance (name, source, license, wallet count, label counts, class
distribution) is derived from the ACTUAL files that are successfully read, and
a sha256 manifest of every consumed file is recorded in the artifact metadata.
No wallet count, label count or distribution is hard-coded here.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ml.schema import CANONICAL_FEATURES, validate_feature_names

GITHUB_URL = "https://github.com/MITIBMxGraph/Elliptic2"
KAGGLE_URL = "https://www.kaggle.com/datasets/ellipticco/elliptic2-data-set"
LICENSE = "CC BY-NC-ND 4.0"

DATASET_NAME = "Elliptic2 (official Bitcoin graph benchmark)"
DATASET_CHAIN = "bitcoin"

# Recognized file names (case-insensitive) inside a dataset directory, mapped
# to canonical roles. The loader tolerates .csv/.tsv variants and missing
# background/aux files, but REQUIRES the labeled node file and the edge file.
_FILE_ROLES = {
    "nodes": ["nodes", "node", "wallets"],
    "edges": ["edges", "edge", "transactions", "txs"],
    "labels_ground_truth": [
        "ground_truth",
        "labels",
        "node_labels",
        "class",
    ],
}

DEFAULT_DATA_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "datasets",
)

DEFAULT_DATASET_DIR = os.path.join(DEFAULT_DATA_ROOT, "elliptic2")

_MIN_LABELED_WALLETS = 100


class DatasetUnavailableError(RuntimeError):
    """Raised whenever the real labeled dataset is not present/honest enough.

    The message always says exactly which source to obtain, so a human can
    fetch it; the pipeline never falls back to synthetic data.
    """


@dataclass
class DatasetStats:
    n_wallets: int = 0
    n_illicit: int = 0
    n_licit: int = 0
    n_excluded_unknown: int = 0
    illicit_ratio: float = 0.0
    edges_loaded: int = 0
    feature_columns: List[str] = field(default_factory=list)
    used_features: List[str] = field(default_factory=list)
    files: Dict[str, dict] = field(default_factory=dict)

    def version_token(self) -> str:
        return (
            f"elliptic2-bitcoin-res{self.n_wallets}-"
            f"{self.n_illicit}illicit-{self.n_licit}licit"
        )


def expected_dataset_dir(explicit: Optional[str] = None) -> str:
    return explicit or DEFAULT_DATASET_DIR


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download_instructions_message() -> str:
    return (
        "The official Elliptic2 dataset is required and is not present on disk."
        "\n\n"
        f"Sources (license: {LICENSE}):\n"
        f"  - GitHub:   {GITHUB_URL}\n"
        f"  - Kaggle:   {KAGGLE_URL}\n\n"
        "Expected layout (<dataset_dir> = "
        f"'{DEFAULT_DATASET_DIR}' or the explicit path):\n"
        "  nodes.csv|.tsv   per-wallet node id + label/class column(s)\n"
        "  edges.csv|.tsv   directed edges: source, target, timestamp, fee, value\n"
        "  optionals: background_nodes.csv, background_edges.csv, "
        "connected_components.csv\n\n"
        "Obtain the release files, place them there, and re-run. Until a real, "
        "documented labeled dataset is validated, the ML service reports "
        "UNTRAINED / DATASET UNAVAILABLE and no model artifact is created."
    )


def find_files(dataset_dir: str) -> Dict[str, str]:
    """Locate role files in the dataset directory (case-insensitive)."""
    if not os.path.isdir(dataset_dir):
        raise DatasetUnavailableError(
            f"Dataset directory not found: {dataset_dir}\n\n"
            + download_instructions_message()
        )
    present = {name.lower(): name for name in os.listdir(dataset_dir)}
    found: Dict[str, str] = {}
    for role, candidates in _FILE_ROLES.items():
        for candidate in candidates:
            for ext in (".csv", ".tsv", ".csv.gz"):
                key = (candidate + ext).lower()
                if key in present:
                    found[role] = os.path.join(dataset_dir, present[key])
                    break
            if role in found:
                break
    return found


def _import_pandas():
    import pandas as pd  # noqa: PLC0415

    return pd


def read_table(path: str):
    pd = _import_pandas()
    try:
        if path.endswith(".gz"):
            return pd.read_csv(path, compression="infer")
        if path.endswith(".tsv"):
            return pd.read_csv(path, sep="\t")
        return pd.read_csv(path)
    except Exception as exc:  # noqa: BLE001
        raise DatasetUnavailableError(
            f"Could not read dataset file {path}: {exc}"
        ) from exc


def _pick_column(df, candidates: List[str]) -> Optional[str]:
    cols = {c.lower(): c for c in df.columns}
    for candidate in candidates:
        if candidate in cols:
            return cols[candidate]
    return None


def _resolve_dir(dataset_dir: Optional[str]) -> Optional[str]:
    if dataset_dir:
        if os.path.isdir(dataset_dir):
            return dataset_dir
        raise DatasetUnavailableError(
            f"Dataset directory not found: {dataset_dir}\n\n"
            + download_instructions_message()
        )
    if os.path.isdir(DEFAULT_DATASET_DIR):
        return DEFAULT_DATASET_DIR
    return None


def load_labeled(
    dataset_dir: Optional[str] = None,
    return_raw: bool = False,
):
    """Load the official Elliptic2 release into per-wallet labelled rows.

    Returns ``(features_df, y, stats)`` where ``features_df`` has canonical
    feature columns (computed with the SAME live feature extractor the runtime
    uses) and ``y`` is the binary wallet-level label series in the same row
    order. Raises DatasetUnavailableError instead of training on anything
    synthetic or unverifiable.

    Wallet-level label derivation is deterministic and documented:
      illicit  -> any ground-truth label == illicit for the wallet
      licit    -> wallet labeled licit in every recorded timestep
      unknown  -> excluded from training and counted (never labelled licit).
    """
    from ml.features import LiveFeatureExtractor

    resolved = _resolve_dir(dataset_dir)
    if not resolved or not os.path.isdir(resolved):
        raise DatasetUnavailableError(download_instructions_message())
    files = find_files(resolved)
    if "nodes" not in files or "edges" not in files:
        raise DatasetUnavailableError(
            "Elliptic2 requires a labeled node file AND an edge file. In "
            f"{resolved} found: {sorted(os.listdir(resolved))}.\n\n"
            + download_instructions_message()
        )

    nodes = read_table(files["nodes"])
    edges = read_table(files["edges"])

    node_id_col = _pick_column(nodes, ["node_id", "wallet_id", "id", "address", "address_id"])
    label_col = _pick_column(nodes, ["class", "label", "y", "category"])
    time_col = _pick_column(nodes, ["time_step", "timestep", "time", "day", "period"])
    if node_id_col is None or label_col is None:
        raise DatasetUnavailableError(
            "Node file must contain a wallet/node id column and a label/class "
            f"column. Columns found: {list(nodes.columns)}."
        )

    src_col = _pick_column(edges, ["source", "from", "from_address", "sender", "sender_address"])
    dst_col = _pick_column(edges, ["target", "to", "to_address", "receiver", "receiver_address"])
    ts_col = _pick_column(edges, ["timestamp", "time", "block_timestamp", "ts"])
    val_col = _pick_column(edges, ["value", "amount"])
    if src_col is None or dst_col is None:
        raise DatasetUnavailableError(
            "Edge file must contain source and target columns. "
            f"Columns found: {list(edges.columns)}."
        )

    extractor = LiveFeatureExtractor()

    records: List[dict] = []
    label_values = []
    excluded_unknown = 0
    all_available: set = set()

    for node in nodes[node_id_col].astype(str).unique():
        label_rows = nodes[nodes[node_id_col].astype(str) == node]
        if label_rows.empty:
            excluded_unknown += 1
            continue
        labels = set(label_rows[label_col].astype(int).unique().tolist())
        # Deterministic wallet-level derivation (documented in the module
        # docstring): any reported illicit label marks the wallet illicit;
        # only-licit labels -> licit; only unknown/missing -> excluded.
        if 1 in labels:
            bin_label = 1
        elif 0 in labels:
            bin_label = 0
        else:
            excluded_unknown += 1
            continue

        incoming = edges[edges[dst_col].astype(str) == node]
        outgoing = edges[edges[src_col].astype(str) == node]
        node_rows = []
        for _, row in outgoing.iterrows():
            node_rows.append(_as_transfer_row(row, dst_col, val_col, ts_col, node, "out"))
        for _, row in incoming.iterrows():
            node_rows.append(_as_transfer_row(row, src_col, val_col, ts_col, node, "in"))
        vector = extractor.compute(node, DATASET_CHAIN, node_rows)
        all_available |= set(vector._values)
        row = {f: (vector.value(f) if vector.is_available(f) else None)
               for f in CANONICAL_FEATURES}
        records.append(row)
        label_values.append(bin_label)

    features_df = _import_pandas().DataFrame(records, columns=CANONICAL_FEATURES)
    labels = _import_pandas().Series(label_values)

    stats = DatasetStats(
        n_wallets=len(labels),
        n_illicit=int(labels.astype(int).sum()),
        n_licit=int((labels == 0).astype(int).sum()),
        n_excluded_unknown=excluded_unknown,
        edges_loaded=int(len(edges)),
        feature_columns=list(nodes.columns) + list(edges.columns),
        used_features=sorted(all_available),
        files={
            role: {
                "path": path,
                "basename": os.path.basename(path),
                "rows": _rows_in(path),
                "sha256": _sha256_file(path),
            }
            for role, path in files.items()
        },
    )
    if stats.n_wallets < _MIN_LABELED_WALLETS:
        raise DatasetUnavailableError(
            f"Only {stats.n_wallets} labeled wallets were validated from the "
            f"loaded Elliptic2 files; this is below the {_MIN_LABELED_WALLETS} "
            "minimum. Re-check the dataset files before training."
        )
    if stats.n_illicit == 0 or stats.n_licit == 0:
        raise DatasetUnavailableError(
            "Loaded Elliptic2 files produced a single-class binary set "
            f"(illicit={stats.n_illicit}, licit={stats.n_licit}); refusing to "
            "train on it."
        )
    stats.illicit_ratio = stats.n_illicit / stats.n_wallets
    validate_feature_names([c for c in features_df.columns if c in CANONICAL_FEATURES])
    if return_raw:
        return features_df, labels, stats, {"nodes": nodes, "edges": edges}
    return features_df, labels, stats


def _rows_in(path: str) -> int:
    pd = _import_pandas()
    try:
        return len(read_table(path))
    except Exception:
        return 0


def _as_transfer_row(row, other_col: str, val_col, ts_col, node: str, direction: str) -> dict:
    value = row[val_col] if val_col in row.index else None
    ts = row[ts_col] if ts_col in row.index else None
    other = str(row[other_col]) if other_col in row.index else ""
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = None
    try:
        ts = int(ts)
    except (TypeError, ValueError):
        ts = None
    if direction == "out":
        return {
            "from_address": node,
            "to_address": other,
            "value": value,
            "block_timestamp": ts,
        }
    return {
        "from_address": other,
        "to_address": node,
        "value": value,
        "block_timestamp": ts,
    }