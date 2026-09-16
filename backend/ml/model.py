"""Trained suspicious-wallet classifier wrapper.

The artifact is a LightGBM binary classifier plus metadata that pins the model
version, the training dataset version, the exact feature set it requires, its
evaluation metrics and the decision threshold. Predictions are strictly
gate-guarded:

* no artifact present  -> status ``not_trained`` (nothing is predicted),
* any required feature missing from the live vector -> status ``unavailable``,
  prediction UNKNOWN / NOT ASSESSED with the missing features listed,
* otherwise -> a probability with top contributing features from the model's
  stored gain importance.

The probability is an estimate of *suspicious wallet activity* — it is never
phrased as criminality and never merged with the VASP attribution score or the
separate sanctions-intelligence block.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ml.schema import validate_feature_names

WARNING_LABEL = "not_assessed"
UNKNOWN_LABEL = "UNKNOWN"

_DISCLAIMER = (
    "Model-estimated suspicious activity probability from a trained "
    "classifier. This is not a determination of criminality, illegality, or "
    "ownership, and it is independent of the analytical VASP attribution score."
)


@dataclass
class Prediction:
    """One wallet's ML output. ``status`` is always explicit."""

    status: str  # trained | not_trained | unavailable
    probability: Optional[float] = None
    label: str = UNKNOWN_LABEL
    level: str = "unknown"
    threshold: Optional[float] = None
    required_features: List[str] = field(default_factory=list)
    missing_features: List[str] = field(default_factory=list)
    top_features: List[dict] = field(default_factory=list)
    model_version: Optional[str] = None
    dataset_version: Optional[str] = None
    chain: Optional[str] = None
    explanation: str = ""
    wording: str = ""
    disclaimer: str = _DISCLAIMER

    def as_dict(self) -> dict:
        data = {
            "status": self.status,
            "probability": self.probability,
            "label": self.label,
            "level": self.level,
            "threshold": self.threshold,
            "required_features": list(self.required_features),
            "missing_features": list(self.missing_features),
            "top_features": list(self.top_features),
            "model_version": self.model_version,
            "dataset_version": self.dataset_version,
            "chain": self.chain,
            "explanation": self.explanation,
            "wording": self.wording,
            "disclaimer": self.disclaimer,
        }
        for key in ("probability", "threshold"):
            if data[key] is None:
                data[key] = None
        return data

    def to_jsonable(self) -> dict:
        return self.as_dict()


class SuspiciousWalletModel:
    """Loadable, version-pinned LightGBM artifact with a hard UNKNOWN gate."""

    def __init__(
        self,
        booster,
        metadata: Dict[str, dict],
        required_features: List[str],
        importances: List[dict],
        threshold: float,
        algorithm: str = "lightgbm",
        dataset: Optional[dict] = None,
        dataset_chain: Optional[str] = None,
        model_name: Optional[str] = None,
        model_disclaimer: Optional[str] = None,
    ) -> None:
        self._booster = booster
        self.model_version = metadata.get("model_version") or "unknown"
        self.dataset_version = metadata.get("dataset_version") or "unknown"
        self.required_features = list(required_features)
        self.importances = list(importances)
        self.threshold = float(threshold)
        self.algorithm = algorithm
        self.dataset = dataset or {}
        self.dataset_chain = (dataset_chain or "").lower() or None
        self.model_name = model_name or ""
        self._disclaimer = model_disclaimer or _DISCLAIMER

    @classmethod
    def from_artifact(cls, artifact_dir: str) -> "SuspiciousWalletModel":
        """Load metadata.json + lightgbm.txt from a saved artifact directory."""
        import os

        meta_path = os.path.join(artifact_dir, "metadata.json")
        with open(meta_path, encoding="utf-8") as fh:
            meta = json.load(fh)

        import lightgbm as lgb

        booster = lgb.Booster(
            model_file=os.path.join(artifact_dir, "lightgbm.txt")
        )
        required = meta["features"]["required"]
        validate_feature_names(required)
        gain = booster.feature_importance("gain")
        names = [meta["features"]["names_ordered"][i] for i in range(len(gain))]
        scored = sorted(
            zip(names, gain), key=lambda pair: pair[1], reverse=True
        )
        importances = [
            {"feature": name, "gain": float(g)}
            for name, g in scored
            if float(g) > 0
        ]
        threshold = float(meta["model"]["threshold"])
        return cls(
            booster=booster,
            metadata=meta,
            required_features=required,
            importances=importances,
            threshold=threshold,
        )

    def _chain_domain_note(self, chain: Optional[str]) -> str:
        """Append a chain-domain note when the live chain differs from the
        training dataset chain. This enforces requirement #10: never claim
        a Bitcoin-trained model is validated for Ethereum/multi-chain."""
        if not chain or not self.dataset_chain:
            return ""
        if chain.lower() == self.dataset_chain:
            return ""
        return (
            f" Trained on Elliptic2 ({self.dataset_chain}) labelled data; "
            f"NOT validated for {chain} or multi-chain inference — treat the "
            "probability as schema-compatible but domain-unvalidated."
        )

    def predict(self, vector, chain: Optional[str] = None) -> Prediction:
        if vector is None:
            return self._unavailable([], chain)
        missing = [f for f in self.required_features if not vector.is_available(f)]
        if missing:
            return self._unavailable(missing, chain)
        row = vector.as_array(self.required_features)
        if row is None:
            return self._unavailable(self.required_features, chain)
        try:
            probability = float(self._booster.predict([row])[0])
        except Exception:
            return self._unavailable(self.required_features, chain)
        probability = max(0.0, min(1.0, probability))
        if probability >= self.threshold:
            label, level = "suspicious", "high"
        else:
            label, level = "not_suspicious", "low"

        top = self.importances[:5]
        chain_note = self._chain_domain_note(chain)
        explanation = (
            f"Model-estimated suspicious activity probability "
            f"{probability:.3f} using {self.algorithm} model "
            f"{self.model_version} trained on dataset "
            f"{self.dataset_version}"
            f" ({len(self.required_features)} features). "
            f"Threshold {self.threshold:.4f} selected on validation split. "
            "Top contributing features: "
            + ", ".join(f"{t['feature']} (gain {t['gain']:.2f})" for t in top)
            + "."
            + chain_note
        )
        disclaimer = self._disclaimer + chain_note
        return Prediction(
            status="trained",
            probability=probability,
            label=label,
            level=level,
            threshold=self.threshold,
            required_features=self.required_features,
            missing_features=[],
            top_features=top,
            model_version=self.model_version,
            dataset_version=self.dataset_version,
            chain=chain,
            explanation=explanation,
            wording=(
                f"Model-estimated suspicious activity probability: {probability:.3f}"
            ),
            disclaimer=disclaimer,
        )

    def _unavailable(self, missing: List[str], chain: Optional[str] = None) -> Prediction:
        chain_note = self._chain_domain_note(chain)
        missing_text = ", ".join(missing) or "all required features"
        return Prediction(
            status="unavailable",
            probability=None,
            label=UNKNOWN_LABEL,
            level=WARNING_LABEL,
            required_features=self.required_features,
            missing_features=missing or self.required_features,
            model_version=self.model_version,
            dataset_version=self.dataset_version,
            chain=chain,
            explanation=(
                "Not assessed: one or more required ML features could not be "
                "computed from the on-chain data available for this wallet "
                f"(missing: {missing_text}). "
                "No values were imputed or fabricated."
                + chain_note
            ),
            wording=(
                "Model-estimated suspicious activity probability: UNKNOWN / "
                "NOT ASSESSED"
                + (" (chain domain differs from training data)" if chain_note else "")
            ),
            disclaimer=self._disclaimer + chain_note,
        )


def not_trained_prediction() -> Prediction:
    """Explicit NOT-TRAINED state used until a genuine artifact exists."""
    return Prediction(
        status="not_trained",
        probability=None,
        label=UNKNOWN_LABEL,
        level=WARNING_LABEL,
        required_features=[],
        missing_features=[],
        model_version=None,
        dataset_version=None,
        explanation=(
            "No trained suspicious-wallet classifier artifact is available in "
            "this deployment. Until a model is genuinely trained and validated "
            "on a documented labeled dataset, ML risk is NOT ASSESSED — no "
            "probability is produced or fabricated."
        ),
        wording=(
            "Model-estimated suspicious activity probability: UNKNOWN / "
            "NOT ASSESSED (no trained model)"
        ),
    )