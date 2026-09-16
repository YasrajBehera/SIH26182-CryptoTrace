"""Deployment-model loader for the packaged trained artifact.

The registry (``ml/registry.py``) loads training-time artifacts stored under
``data/models/<version>/`` as LightGBM text dumps. The deployment model instead
ships as a single pickled sklearn ``LGBMClassifier`` plus ``metadata.json`` in
``backend/ml/models/``:

    cryptotrace_elliptic2_lightgbm.joblib   the trained classifier
    metadata.json                            version, dataset, threshold, schema
    MODEL_CARD.md                            documented limitations
    SHA256SUMS.json                          integrity checksums

``load_deployment_model()`` resolves that directory (overridable via the
``CRYPTOTRACE_MODEL_DIR`` env var), loads the joblib exactly once per
(dir, mtime) pair, and exposes it as a ``SuspiciousWalletModel``. It returns
None (honestly) when the package is absent or unreadable — the caller then
falls back to the training registry or reports ``not_trained``.

Crucially, it does not fabricate any live features: the model only becomes
usable when every feature listed in ``metadata.json`` is present in
``CANONICAL_FEATURES`` and computable by ``LiveFeatureExtractor``.
"""

from __future__ import annotations

import json
import os
from typing import List, Optional

from ml.model import SuspiciousWalletModel
from ml.schema import CANONICAL_FEATURES

# backend/ml/models
DEFAULT_MODEL_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "models",
)

_ARTIFACT_FILE = "cryptotrace_elliptic2_lightgbm.joblib"
_METADATA_FILE = "metadata.json"

_SENTINEL = object()
_cache: dict = {}


class _JoblibPredictor:
    """Minimal adapter exposing the .predict(rows) contract model.py expects.

    ``rows`` is a list of numeric rows in required-feature order; the adapter
    returns the estimated *suspicious* (positive-class) probability for each.
    """

    def __init__(self, estimator, positive_index: int) -> None:
        import numpy as np  # noqa: PLC0415

        self._est = estimator
        self._pos_index = positive_index
        self._np = np

    def predict(self, rows: List[List[float]]) -> List[float]:
        import numpy as np  # noqa: PLC0415

        matrix = np.asarray(rows, dtype=float)
        proba = self._est.predict_proba(matrix)
        if proba.ndim == 2:
            return [float(v) for v in proba[:, self._pos_index]]
        return [float(v) for v in proba]

    def gain_importances(self) -> List[dict]:
        booster = getattr(self._est, "booster_", None)
        if booster is not None:
            try:
                importances = booster.feature_importance("gain")
            except Exception:
                importances = None
        else:
            try:
                importances = self._est.feature_importances_
            except Exception:
                importances = None
        names = list(getattr(self._est, "feature_name_", None) or [])
        if importances is None or len(importances) != len(names):
            return []
        ranked = sorted(
            zip(names, importances),
            key=lambda pair: pair[1],
            reverse=True,
        )
        return [
            {"feature": name, "gain": float(gain)}
            for name, gain in ranked
            if float(gain) > 0
        ]


def deployment_model_dir() -> Optional[str]:
    env_dir = os.environ.get("CRYPTOTRACE_MODEL_DIR")
    if env_dir:
        return env_dir if os.path.isdir(env_dir) else None
    return DEFAULT_MODEL_DIR if os.path.isdir(DEFAULT_MODEL_DIR) else None


def _metadata_path(directory: str) -> str:
    return os.path.join(directory, _METADATA_FILE)


def _artifact_path(directory: str) -> str:
    return os.path.join(directory, _ARTIFACT_FILE)


def load_deployment_model() -> Optional[SuspiciousWalletModel]:
    """Load the packaged model once, keyed by (dir, mtime). Returns None when
    the deployment package is absent or cannot be interpreted honestly."""
    directory = deployment_model_dir()
    if directory is None:
        return None
    meta_path = _metadata_path(directory)
    artifact_path = _artifact_path(directory)
    if not os.path.isfile(meta_path) or not os.path.isfile(artifact_path):
        return None
    try:
        cache_key = (directory, os.path.getmtime(meta_path), os.path.getmtime(artifact_path))
    except OSError:
        return None
    if cache_key in _cache:
        cached = _cache[cache_key]
        return None if cached is _SENTINEL else cached

    result = _build_model(meta_path, artifact_path)
    _cache[cache_key] = result if result is not None else _SENTINEL
    return result


def _build_model(
    meta_path: str, artifact_path: str
) -> Optional[SuspiciousWalletModel]:
    try:
        with open(meta_path, encoding="utf-8") as fh:
            meta = json.load(fh)
        import joblib  # noqa: PLC0415

        estimator = joblib.load(artifact_path)
    except Exception:
        return None

    required_features: List[str] = [
        f for f in (meta.get("features") or []) if isinstance(f, str)
    ]
    if not required_features:
        return None
    unknown_required = [f for f in required_features if f not in CANONICAL_FEATURES]
    if unknown_required:
        # The live extractor can never produce these; refusing is more honest
        # than silently returning a probability on an incompatible schema.
        return None

    classes = getattr(estimator, "classes_", None)
    if classes is None:
        classes = [0, 1]
    classes = list(classes)
    positive_index = classes.index(1) if 1 in classes else len(classes) - 1
    predictor = _JoblibPredictor(estimator, positive_index)
    importances = predictor.gain_importances()

    dataset = meta.get("dataset") or {}
    chain = dataset.get("chain", "Bitcoin")
    name = dataset.get("name", "Elliptic2")
    label_column = dataset.get("label_column", "unknown")
    dataset_version = f"{name}:{chain}:{label_column}"

    model_version = str(meta.get("model_version") or "1.0.0")
    threshold = float((meta.get("threshold") or {}).get("value", 0.5))
    algorithm = str(meta.get("algorithm") or "LightGBM")
    disclaimer = (
        "Model-estimated suspicious activity probability from a trained "
        f"{algorithm} classifier (model {model_version}). This is not a "
        "determination of criminality, illegality, or ownership, and it is "
        "independent of the analytical VASP attribution score. Trained on the "
        f"Elliptic2 ({chain}) labelled dataset; NOT validated for Ethereum or "
        "multi-chain inference."
    )

    return SuspiciousWalletModel(
        booster=predictor,
        metadata={"model_version": model_version, "dataset_version": dataset_version},
        required_features=required_features,
        importances=importances,
        threshold=threshold,
        algorithm=algorithm,
        dataset=dataset,
        dataset_chain=chain,
        model_name=str(meta.get("model_name") or ""),
        model_disclaimer=disclaimer,
    )