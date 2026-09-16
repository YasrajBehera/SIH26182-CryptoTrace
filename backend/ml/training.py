"""Training + evaluation + artifact creation.

Honest-by-construction:

* requires the OFFICIAL Elliptic2 release on disk (``ml.dataset.load_labeled``);
  without it the runner raises DatasetUnavailableError and creates NO artifact —
  there is no synthetic fallback anywhere,
* per-wallet features are computed with the SAME live feature extractor the
  runtime uses, so train and live feature semantics are identical,
* wallets whose features cannot be fully computed are counted and excluded
  (they would be UNKNOWN at live inference too),
* rows are split into train / validation / test with the test set untouched
  until the very end: LightGBM early-stopping and the decision threshold are
  both chosen on the VALIDATION split only; all reported metrics are computed
  ONCE on the untouched test split,
* class imbalance is handled with ``scale_pos_weight`` and evaluated with
  precision / recall / F1 / ROC-AUC / PR-AUC / confusion matrix — never
  accuracy alone,
* dataset provenance (name, source, license, wallet counts, class distribution,
  file sha256 manifest) is read from the actual loaded files at load time.

Run::

    python -m ml.training <elliptic2_dataset_dir>        (default: data/datasets/elliptic2)
"""

from __future__ import annotations

import json
from typing import Dict, Optional

from ml.dataset import (
    DATASET_CHAIN,
    DATASET_NAME,
    DatasetUnavailableError,
    GITHUB_URL,
    KAGGLE_URL,
    LICENSE,
    load_labeled,
)
from ml.model_card import build_model_card as build_card
from ml.schema import CANONICAL_FEATURES, validate_feature_names
from ml import registry

VALIDATION_FRACTION = 0.15
TEST_FRACTION = 0.15
DEFAULT_SEED = 42
ALGORITHM = "lightgbm"
_MIN_FEATURES_REQUIRED = 8

_LGB_PARAMS = {
    "objective": "binary",
    "metric": ["auc", "average_precision", "binary_logloss"],
    "boosting_type": "gbdt",
    "num_leaves": 63,
    "learning_rate": 0.05,
    "min_data_in_leaf": 20,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "verbosity": -1,
    "seed": DEFAULT_SEED,
}


class TrainingError(RuntimeError):
    pass


def _split_3way(x, y, seed: int):
    """Stratified train/validation/test split (no leakage between splits)."""
    from sklearn.model_selection import train_test_split

    x_tr_val, x_te, y_tr_val, y_te = train_test_split(
        x, y, test_size=TEST_FRACTION, stratify=y, random_state=seed
    )
    val_size = VALIDATION_FRACTION / (1.0 - TEST_FRACTION)
    x_tr, x_val, y_tr, y_val = train_test_split(
        x_tr_val, y_tr_val, test_size=val_size, stratify=y_tr_val,
        random_state=seed + 1,
    )
    return x_tr, x_val, x_te, y_tr, y_val, y_te


def train_model(
    dataset_dir: Optional[str] = None,
    out_root: Optional[str] = None,
    seed: int = DEFAULT_SEED,
    model_major: int = 0,
) -> Dict:
    """Train the suspicious-wallet classifier on the real Elliptic2 release.

    Raises DatasetUnavailableError / TrainingError and creates nothing whenever
    the labelled dataset is missing, invalid, or single-class.
    """
    x, y, stats = load_labeled(dataset_dir)

    if len(x) == 0 or len(y) == 0:
        raise TrainingError("No labelled wallets produced by the dataset load.")

    # Feature set = canonical features available for EVERY retained wallet.
    # A wallet missing any of them is excluded (it would be UNKNOWN live).
    available = x.notna().all(axis=0)
    required = [c for c in CANONICAL_FEATURES if c in x.columns and available[c]]
    if len(required) < _MIN_FEATURES_REQUIRED:
        raise TrainingError(
            f"Only {len(required)} canonical features are computable across the "
            f"loaded dataset (minimum {_MIN_FEATURES_REQUIRED}). The live "
            "extractor and dataset must agree on the feature schema."
        )
    validate_feature_names(required)
    x = x[required].copy()
    complete = x.notna().all(axis=1)
    n_excluded = int((~complete).sum())
    x, y = x[complete], y[complete]

    import lightgbm as lgb  # noqa: PLC0415

    y_bin = y.astype(int).values
    x_np = x.values.astype(float)

    x_tr, x_val, x_te, y_tr, y_val, y_te = _split_3way(x_np, y_bin, seed)
    pos_train = int(y_tr.sum())
    neg_train = int(len(y_tr)) - pos_train
    if pos_train == 0 or neg_train == 0:
        raise TrainingError("Train split is single-class; cannot train.")

    scale_pos_weight = neg_train / pos_train
    params = dict(_LGB_PARAMS)
    params["scale_pos_weight"] = scale_pos_weight
    params["seed"] = seed

    dtr = lgb.Dataset(x_tr, label=y_tr, feature_name=list(required))
    dval = lgb.Dataset(x_val, label=y_val, reference=dtr)
    booster = lgb.train(
        params,
        dtr,
        num_boost_round=500,
        valid_sets=[dval],
        callbacks=[lgb.early_stopping(80, verbose=False)],
    )

    val_proba = booster.predict(x_val, num_iteration=booster.best_iteration)
    threshold = _pick_threshold_on_validation(y_val, val_proba)
    if threshold is None:
        raise TrainingError("Could not select a decision threshold on validation.")

    # Evaluation is performed exactly ONCE, on the untouched test split.
    from sklearn.metrics import (  # noqa: PLC0415
        average_precision_score,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    test_proba = booster.predict(x_te, num_iteration=booster.best_iteration)
    pred = (test_proba >= threshold).astype(int)
    metrics = {
        "precision": float(precision_score(y_te, pred, zero_division=0)),
        "recall": float(recall_score(y_te, pred, zero_division=0)),
        "f1": float(f1_score(y_te, pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_te, test_proba)),
        "pr_auc": float(average_precision_score(y_te, test_proba)),
        "threshold": float(threshold),
        "threshold_selected_on": "validation",
        "confusion_matrix": confusion_matrix(y_te, pred).tolist(),
        "train_rows": int(len(x_tr)),
        "validation_rows": int(len(x_val)),
        "test_rows": int(len(x_te)),
        "positives_test": int(y_te.sum()),
        "positives_validation": int(y_val.sum()),
    }

    gain = booster.feature_importance("gain")
    names = list(required)
    scored = sorted(zip(names, gain), key=lambda p: p[1], reverse=True)
    top = [{"feature": name, "gain": float(g)} for name, g in scored if g > 0][:10]

    model_version = registry.new_model_version(major=model_major)
    metadata = _build_metadata(
        model_version=model_version,
        stats=stats,
        required=required,
        test_size=TEST_FRACTION,
        val_size=VALIDATION_FRACTION,
        seed=seed,
        scale_pos_weight=scale_pos_weight,
        threshold=threshold,
        best_iteration=int(booster.best_iteration),
        metrics=metrics,
        top=top,
        n_excluded_missing_features=n_excluded,
    )

    card = build_card(metadata)
    artifact_dir = registry.save_artifact(
        model_version=model_version,
        metadata=metadata,
        metrics=metrics,
        importances=top,
        booster=booster,
        model_card_md=card,
        root=out_root,
    )
    return {
        "model_version": model_version,
        "dataset_version": stats.version_token(),
        "artifact_dir": artifact_dir,
        "metrics": metrics,
        "feature_count": len(required),
        "top_features": top,
    }


def _build_metadata(
    model_version: str,
    stats,
    required,
    test_size: float,
    val_size: float,
    seed: int,
    scale_pos_weight: float,
    threshold: float,
    best_iteration: int,
    metrics: dict,
    top: list,
    n_excluded_missing_features: int,
) -> dict:
    """Dataset provenance comes entirely from the actually-loaded dataset."""
    dataset = {
        "name": DATASET_NAME,
        "chain": DATASET_CHAIN,
        "source_github": GITHUB_URL,
        "source_kaggle": KAGGLE_URL,
        "license": LICENSE,
        "labels": "binary derived from Elliptic2 ground truth "
        "(any-illicit -> illicit; only-licit -> licit; "
        "unknown excluded)",
        "n_wallets": int(stats.n_wallets),
        "n_illicit": int(stats.n_illicit),
        "n_licit": int(stats.n_licit),
        "n_excluded_unknown_label": int(stats.n_excluded_unknown),
        "n_excluded_missing_features": int(n_excluded_missing_features),
        "illicit_ratio": float(stats.illicit_ratio),
        "edges_loaded": int(stats.edges_loaded),
        "train_rows": int(metrics["train_rows"]),
        "validation_rows": int(metrics["validation_rows"]),
        "test_rows": int(metrics["test_rows"]),
        "test_fraction": float(test_size),
        "validation_fraction": float(val_size),
        "seed": int(seed),
        "files": stats.files,
    }
    return {
        "model_version": model_version,
        "dataset_version": stats.version_token(),
        "created_at": _now_iso(),
        "algorithm": ALGORITHM,
        "dataset": dataset,
        "features": {
            "schema_version": 1,
            "total": len(required),
            "required": list(required),
            "names_ordered": list(required),
        },
        "model": {
            "algorithm": ALGORITHM,
            "objective": "binary",
            "eval_metric": "auc, average_precision, binary_logloss",
            "scale_pos_weight": float(scale_pos_weight),
            "threshold": float(threshold),
            "threshold_selected_on": "validation",
            "best_iteration": int(best_iteration),
            "top_features": top,
        },
        "metrics": {
            **metrics,
            "threshold_selected_on": "validation",
        },
    }


def _pick_threshold_on_validation(y_val, proba) -> Optional[float]:
    """Pick the best-F1 decision threshold on VALIDATION (never test)."""
    import numpy as np  # noqa: PLC0415
    from sklearn.metrics import f1_score

    y_val = np.asarray(y_val)
    proba = np.asarray(proba, dtype=float)
    best_t, best_f1 = None, -1.0
    for t in _candidate_thresholds(proba):
        p = (proba >= t).astype(int)
        if len(set(p.tolist())) == 1:
            continue
        f1 = f1_score(y_val, p, zero_division=0)
        if f1 > best_f1:
            best_t, best_f1 = t, f1
    return best_t


def _candidate_thresholds(proba):
    """Candidate thresholds spanning the observed probability range."""
    step = 0.05
    lo = 0.05
    candidates = []
    t = lo
    while t <= 0.95 + 1e-9:
        candidates.append(round(t, 2))
        t += step
    return candidates


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _cli_main() -> None:
    import sys

    if len(sys.argv) > 2:
        print(f"usage: python -m ml.training [elliptic2_dataset_dir] ({sys.argv[0]})")
        raise SystemExit(2)
    dataset_dir = sys.argv[1] if len(sys.argv) == 2 else None
    try:
        result = train_model(dataset_dir=dataset_dir)
    except DatasetUnavailableError as exc:
        print(f"DATASET UNAVAILABLE: {exc}", file=sys.stderr)
        raise SystemExit(3)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    _cli_main()