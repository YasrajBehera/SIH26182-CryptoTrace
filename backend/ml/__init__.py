"""Explainable ML suspicious-wallet risk classifier.

Runtime components (feature extraction, prediction gate, registry, service)
import nothing heavier than the standard library plus the curated intelligence
set, so the API stays fast when no trained model is present. Training-only
dependencies (pandas, scikit-learn, lightgbm) are imported lazily inside
``ml.training`` and never at package import time.
"""

from ml.schema import CANONICAL_FEATURES
from ml.service import MLRiskService, ml_analysis_id, ml_evidence_id

__all__ = [
    "CANONICAL_FEATURES",
    "MLRiskService",
    "ml_analysis_id",
    "ml_evidence_id",
]