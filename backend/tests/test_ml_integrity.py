"""ML integrity tests.

These tests pin the HONEST behaviour of the ML layer:

* no trained artifact  -> explicit ``not_trained`` / UNKNOWN, never a fake
  probability,
* live feature extraction never imputes: uncomputable features are missing and
  force UNKNOWN at prediction time,
* the ``sanctions_exact_match`` feature reflects a REAL curated public record,
* evidence records pin model_version + dataset_version in provenance,
* the ML risk block is SEPARATE from the analytical VASP score and the
  criminal/sanctions block,
* threshold selection happens on validation, and it is only ever applied once
  against the untouched test split (the helper is exercised directly here —
  no training run happens in this suite),
* training refuses to start when the official labelled dataset is unavailable
  (DatasetUnavailableError, no artifact created).

No synthetic dataset is used and no real model is trained in this file.
"""

import os
from pathlib import Path

import pytest

from ml.features import FeatureVector, LiveFeatureExtractor
from ml.model import Prediction, SuspiciousWalletModel
from ml.service import MLRiskService
from ml import registry


def _address(suffix_hex: str) -> str:
    return "0x" + suffix_hex.zfill(40)


def _transfers_for(target: str) -> list:
    """3 real transfers touching ``target`` (2 outbound, 1 inbound)."""
    peer_a = _address("aaaa")
    peer_b = _address("bbbb")
    return [
        {"from_address": target, "to_address": peer_a, "value": "5.0",
         "block_timestamp": 1704067200},
        {"from_address": target, "to_address": peer_b, "value": "2.5",
         "block_timestamp": 1704067500},
        {"from_address": peer_a, "to_address": target, "value": "1.0",
         "block_timestamp": 1704140000},
    ]


class TestNotTrainedGate:
    def test_no_artifact_means_not_trained(self, tmp_path):
        service = MLRiskService(registry_root=str(tmp_path))
        result = service.assess(_address("cafe"), "eth")
        assert result["status"] == "not_trained"
        assert result["probability"] is None
        assert result["label"] == "UNKNOWN"
        assert result["model_version"] is None
        assert result["dataset_version"] is None
        assert "UNKNOWN" in result["wording"]

    def test_registry_empty_dir_is_not_an_artifact(self, tmp_path):
        assert registry.load_latest(root=str(tmp_path)) is None
        assert registry.artifact_dirs(root=str(tmp_path)) == []


class TestLiveExtractorNoFabrication:
    def test_empty_history_has_uncomputable_features_missing(self):
        target = _address("1111")
        vector = LiveFeatureExtractor().compute(target, "eth", [])
        assert vector.value("tx_count") == 0
        assert not vector.is_available("avg_value")
        assert not vector.is_available("incoming_volume")
        assert not vector.is_available("tx_per_day_frequency")
        # Counts and exposure are truly 0 (no counterparties, no values
        # observed) — those are real observations, not guesses.
        assert vector.value("unique_counterparties") == 0
        assert "avg_value" in vector.missing_names

    def test_full_history_is_real_and_finite(self):
        target = _address("2222")
        vector = LiveFeatureExtractor().compute(target, "eth", _transfers_for(target))
        assert vector.value("tx_count") == 3
        assert vector.value("unique_counterparties") == 2
        assert vector.value("incoming_count") == 1
        assert vector.value("outgoing_count") == 2
        assert vector.is_available("avg_value")
        assert vector.is_available("tx_per_day_frequency")
        for name in vector.feature_names():
            if vector.is_available(name):
                value = vector.value(name)
                assert value is not None
                assert value == value  # not NaN
                assert abs(value) != float("inf")

    def test_sanctions_exact_match_from_real_curated_record(self):
        # The Lazarus Group address is a REAL curated public (OFAC) record in
        # intelligence.curated_sanctions; the feature must reflect it.
        from intelligence.curated_sanctions import load_curated_sanctions_directory

        repo = load_curated_sanctions_directory()
        assert len(repo.all_records()) >= 1
        curated = repo.all_records()[0]
        vector = LiveFeatureExtractor().compute(
            curated.address, curated.chain, _transfers_for(curated.address)
        )
        assert vector.value("sanctions_exact_match") == 1.0
        plain = LiveFeatureExtractor().compute(_address("9999"), "eth", [])
        assert plain.value("sanctions_exact_match") == 0.0


class _StubBooster:
    """Booster stand-in for unit tests only; predict() is never reached on the
    unavailable path (the test asserts exactly that)."""

    def __init__(self, probability: float):
        self._probability = probability

    def predict(self, rows):
        return [self._probability]


class TestUnknownGateWhenFeaturesMissing:
    def test_unavailable_when_required_feature_missing(self):
        model = SuspiciousWalletModel(
            booster=_StubBooster(0.9),
            metadata={"model_version": "lightgbm-0.0.0",
                      "dataset_version": "elliptic2-bitcoin-res-test"},
            required_features=["tx_count", "avg_value", "degree"],
            importances=[{"feature": "tx_count", "gain": 3.0}],
            threshold=0.5,
        )
        vector = FeatureVector({"tx_count": 1.0}, {"avg_value", "degree"})
        prediction = model.predict(vector)
        assert prediction.status == "unavailable"
        assert prediction.probability is None
        assert prediction.label == "UNKNOWN"
        assert "avg_value" in prediction.missing_features
        assert "degree" in prediction.missing_features
        assert "UNKNOWN" in prediction.wording

    def test_trained_prediction_is_separate_and_explained(self):
        model = SuspiciousWalletModel(
            booster=_StubBooster(0.91),
            metadata={"model_version": "lightgbm-0.0.0",
                      "dataset_version": "elliptic2-bitcoin-res-test"},
            required_features=["tx_count"],
            importances=[{"feature": "tx_count", "gain": 3.0}],
            threshold=0.5,
        )
        vector = FeatureVector({"tx_count": 3.0}, set())
        prediction = model.predict(vector)
        assert prediction.status == "trained"
        assert prediction.probability == pytest.approx(0.91)
        assert prediction.label == "suspicious"
        # Wording is carefully non-criminal: "estimated suspicious activity".
        assert "Model-estimated suspicious activity probability" in prediction.wording
        assert "criminal" not in prediction.wording


class TestThresholdOnValidationNotTest:
    def test_threshold_picker_is_validation_based(self):
        from ml.training import _pick_threshold_on_validation

        y = [0, 0, 0, 0, 1, 1, 1, 1]
        proba = [0.05, 0.1, 0.15, 0.2, 0.85, 0.87, 0.9, 0.95]
        threshold = _pick_threshold_on_validation(y, proba)
        assert threshold is not None
        assert 0.2 <= threshold <= 0.85

    def test_metadata_documents_validation_based_threshold(self):
        # The metadata builder records where the threshold came from so a model
        # card / evidence trail always states the methodology.
        from ml.training import _build_metadata
        from ml.dataset import DatasetStats

        stats = DatasetStats(n_wallets=1000, n_illicit=300, n_licit=700,
                             edges_loaded=5000,
                             used_features=["tx_count", "avg_value"])
        meta = _build_metadata(
            model_version="lightgbm-0.0.0", stats=stats,
            required=["tx_count", "avg_value"],
            test_size=0.15, val_size=0.15, seed=42,
            scale_pos_weight=2.3, threshold=0.55, best_iteration=120,
            metrics={"train_rows": 700, "validation_rows": 150,
                     "test_rows": 150, "positives_test": 40,
                     "positives_validation": 45},
            top=[{"feature": "tx_count", "gain": 2.0}],
            n_excluded_missing_features=0,
        )
        assert meta["model"]["threshold_selected_on"] == "validation"
        assert meta["metrics"]["threshold_selected_on"] == "validation"
        assert meta["dataset"]["source_github"].endswith("MITIBMxGraph/Elliptic2")
        assert meta["dataset"]["license"] == "CC BY-NC-ND 4.0"
        # Provenance comes from the (mock) loaded stats, not hard-coded counts.
        assert meta["dataset"]["n_wallets"] == 1000


class TestEvidenceVersions:
    def test_ml_evidence_pins_model_and_dataset_versions(self):
        from evidence.models import EvidenceType
        from evidence.repository import EvidenceRepository
        from evidence.service import EvidenceService
        from ml.service import ml_evidence_id

        service = EvidenceService(repository=EvidenceRepository())
        record = service.create_evidence(
            attribution_id="ml-test",
            evidence_type=EvidenceType.ML_PREDICTION,
            address=_address("cafe"),
            chain="eth",
            confidence=0.91,
            description="Trained model prediction.",
            source="ml",
            method="lightgbm_classifier_lightgbm-0.0.0",
            source_type="ml_model",
            model_version="lightgbm-0.0.0",
            dataset_version="elliptic2-bitcoin-res-test",
            evidence_id=ml_evidence_id(_address("cafe")),
        )
        assert record.provenance.model_version == "lightgbm-0.0.0"
        assert record.provenance.dataset_version == "elliptic2-bitcoin-res-test"
        dumped = record.provenance.model_dump()
        assert "model_version" in dumped and "dataset_version" in dumped
        assert record.evidence_type == EvidenceType.ML_PREDICTION


class TestRiskSeparation:
    def test_ml_block_is_separate_from_vasp_and_sanctions(self, tmp_path):
        from risk.repository import MemoryRiskRepository
        from risk.service import RiskService

        service = RiskService(
            repository=MemoryRiskRepository(),
            ml_service=MLRiskService(registry_root=str(tmp_path)),
        )
        target = _address("cafe")
        assessment = service.evaluate(
            address=target,
            chain="eth",
            candidates=[{"score": 15.5, "confidence": "LOW",
                         "score_breakdown": {"known_address_match": 0}}],
            transfers=_transfers_for(target),
            evidence_count=2,
            investigation_id="inv-1",
        )
        assert assessment.ml_assessment is not None
        assert assessment.ml_assessment["status"] == "not_trained"
        assert assessment.ml_assessment["probability"] is None
        # The analytical VASP/attribution score is UNCHANGED by the ML block.
        assert assessment.risk_score >= 0
        assert assessment.criminal_intelligence is None
        assert assessment.ml_assessment["label"] == "UNKNOWN"

    def test_ml_assessment_survives_memory_persistence(self, tmp_path):
        from risk.repository import MemoryRiskRepository
        from risk.service import RiskService

        repo = MemoryRiskRepository()
        service = RiskService(
            repository=repo,
            ml_service=MLRiskService(registry_root=str(tmp_path)),
        )
        target = _address("cafe")
        assessment = service.evaluate(
            address=target, chain="eth", candidates=[], transfers=[],
            evidence_count=0, investigation_id="inv-2",
        )
        service.persist(assessment)
        loaded = repo.get_latest("inv-2")
        assert loaded.ml_assessment is not None
        assert loaded.ml_assessment["status"] == "not_trained"


class TestDeploymentArtifact:
    """Exercises the REAL packaged model at backend/ml/models.

    The suite-wide autouse fixture pins CRYPTOTRACE_MODEL_DIR to a nonexistent
    path; these tests deliberately point it back at the shipped artifact and
    verify it loads, predicts on live features, stays honest when required
    features are missing, and never represents itself as validated for a chain
    other than the Bitcoin/Elliptic2 dataset it was trained on.
    """

    MODEL_DIR = str(
        Path(__file__).resolve().parents[2] / "backend" / "ml" / "models"
    )

    def test_loader_loads_real_joblib(self, monkeypatch):
        from ml.artifact_loader import load_deployment_model

        monkeypatch.setenv("CRYPTOTRACE_MODEL_DIR", self.MODEL_DIR)
        model = load_deployment_model()
        assert model is not None
        assert model.model_version == "1.0.0"
        assert model.dataset_chain == "bitcoin"
        assert "Elliptic2:Bitcoin" in model.dataset_version
        assert set(model.required_features) == {
            "outgoing_count",
            "incoming_count",
            "tx_count",
            "unique_counterparties",
        }
        assert model.threshold == 0.05

    def test_loader_returns_none_for_missing_dir(self, monkeypatch, tmp_path):
        from ml.artifact_loader import load_deployment_model

        monkeypatch.setenv("CRYPTOTRACE_MODEL_DIR", str(tmp_path / "nope"))
        assert load_deployment_model() is None

    def test_real_model_predicts_on_live_features(self, monkeypatch):
        from ml.artifact_loader import load_deployment_model

        monkeypatch.setenv("CRYPTOTRACE_MODEL_DIR", self.MODEL_DIR)
        model = load_deployment_model()
        target = _address("cafe")
        vector = LiveFeatureExtractor().compute(
            target, "eth", _transfers_for(target)
        )
        pred = model.predict(vector, chain="eth")
        assert pred.status == "trained"
        assert pred.probability is not None and 0.0 <= pred.probability <= 1.0
        assert pred.model_version == "1.0.0"
        assert "Elliptic2:Bitcoin" in pred.dataset_version
        assert "NOT validated for eth" in pred.explanation
        assert "NOT validated for eth" in pred.disclaimer
        assert any(
            t["feature"] in model.required_features for t in pred.top_features
        )

    def test_real_model_gates_on_missing_required_feature(self, monkeypatch):
        from ml.artifact_loader import load_deployment_model

        monkeypatch.setenv("CRYPTOTRACE_MODEL_DIR", self.MODEL_DIR)
        model = load_deployment_model()
        vector = FeatureVector(
            values={
                "outgoing_count": 1.0,
                "incoming_count": 0.0,
                "tx_count": 1.0,
                "unique_counterparties": 1.0,
            },
            missing={"tx_count"},
        )
        pred = model.predict(vector, chain="eth")
        assert pred.status == "unavailable"
        assert pred.probability is None
        assert pred.label == "UNKNOWN"
        assert "tx_count" in pred.missing_features

    def test_real_model_service_assessment_is_trained(self, monkeypatch):
        from ml.service import MLRiskService

        monkeypatch.setenv("CRYPTOTRACE_MODEL_DIR", self.MODEL_DIR)
        result = MLRiskService().assess(_address("cafe"), "eth", _transfers_for(_address("cafe")))
        assert result["status"] == "trained"
        assert result["model_version"] == "1.0.0"
        assert result["chain"] == "eth"


class TestTrainingRequiresRealDataset:
    def test_no_dataset_no_training_no_artifact(self, tmp_path):
        from ml.dataset import DatasetUnavailableError
        from ml.training import train_model

        with pytest.raises(DatasetUnavailableError):
            train_model(
                dataset_dir=os.path.join(str(tmp_path), "missing-elliptic2"),
                out_root=os.path.join(str(tmp_path), "models"),
            )
        assert registry.artifact_dirs(
            root=os.path.join(str(tmp_path), "models")
        ) == []

    def test_dataset_instructions_name_official_source(self):
        from ml.dataset import download_instructions_message

        message = download_instructions_message()
        assert "MITIBMxGraph/Elliptic2" in message
        assert "ellipticco/elliptic2-data-set" in message
        assert "CC BY-NC-ND 4.0" in message