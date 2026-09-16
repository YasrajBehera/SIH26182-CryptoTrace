"""ML risk service: ties the live feature extractor to a trained artifact.

The service is the single entry point that other modules (risk, cases,
evidence, reports) use to obtain the ML risk signal. It is honest about its
state: with no trained artifact in the registry it returns an explicit
``not_trained`` status and never fabricates a probability.
"""

from __future__ import annotations

import hashlib
from typing import List, Optional

from ml.features import FeatureVector, LiveFeatureExtractor
from ml.model import SuspiciousWalletModel, not_trained_prediction
from ml.registry import load_latest


def ml_evidence_id(address: str, chain: str = "eth") -> str:
    digest = hashlib.sha1(f"ml:{chain}:{address}".lower().encode()).hexdigest()[:12]
    return f"ev-ml-{digest}"


def ml_analysis_id(address: str, chain: str = "eth") -> str:
    digest = hashlib.sha1(
        f"ml-analysis:{chain}:{address}".lower().encode()
    ).hexdigest()[:12]
    return f"ml-{digest}"


_UNSET = object()


class MLRiskService:
    def __init__(
        self,
        registry_root: Optional[str] = None,
        extractor: Optional[LiveFeatureExtractor] = None,
    ) -> None:
        self._root = registry_root
        self._extractor = extractor or LiveFeatureExtractor()
        self._model: Optional[SuspiciousWalletModel] = None
        self._model_loaded_for: object = _UNSET

    @property
    def model(self) -> Optional[SuspiciousWalletModel]:
        """Resolve the active model once.

        With no pinned ``registry_root`` the packaged deployment model
        (``backend/ml/models/``) is preferred; otherwise the newest training
        artifact from the registry is used. Either way the first resolution is
        cached until ``reset()``.
        """
        if self._model is not None:
            return self._model
        if self._model_loaded_for is self._root:
            return self._model
        if self._root is None:
            from ml.artifact_loader import load_deployment_model

            self._model = load_deployment_model()
        if self._model is None:
            self._model = load_latest(root=self._root)
        self._model_loaded_for = self._root
        return self._model

    @property
    def model_status(self) -> str:
        return "trained" if self.model is not None else "not_trained"

    def extract(self, address: str, chain: str, transfers=None) -> FeatureVector:
        return self._extractor.compute(address, chain, transfers)

    def assess(
        self,
        address: str,
        chain: str = "eth",
        transfers=None,
    ) -> dict:
        """Full ML assessment dict for a wallet (never raises on data gaps)."""
        model = self.model
        if model is None:
            return not_trained_prediction().as_dict()
        vector = self.extract(address, chain, transfers)
        return model.predict(vector, chain=chain).as_dict()

    def model_version_and_dataset(self) -> dict:
        model = self.model
        if model is None:
            return {"model_version": None, "dataset_version": None}
        return {
            "model_version": model.model_version,
            "dataset_version": model.dataset_version,
        }

    def reset(self) -> None:
        self._model = None
        self._model_loaded_for = _UNSET