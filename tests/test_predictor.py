"""Exercise the saved-bundle adapter with real serialization and shared features."""
import numpy as np
import pandas as pd
import pytest

from backend.schemas import PredictionResponse
from speedmap import artifacts, config
from speedmap.inference.predictor import Predictor


class ConstantEstimator:
    def __init__(self, value):
        self.value = value
        self.last_features = None

    def predict(self, features):
        self.last_features = features.copy()
        return np.full(len(features), self.value)


class FixedInterval:
    def interval(self, predictions):
        return predictions - 20, predictions + 20


@pytest.fixture
def saved_model(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARTIFACTS_MODELS", tmp_path)
    towers = pd.DataFrame({
        "tower_id": [1, 2, 3], "latitude": [21.0285, 21.03, 21.04],
        "longitude": [105.8542, 105.85, 105.86],
    })
    cells = pd.DataFrame({"latitude": [21.0285, 21.03], "longitude": [105.8542, 105.85], "operator": [1, 4]})
    tiles = pd.DataFrame({"quadkey": ["x"], "latitude": [21.029], "longitude": [105.855], "devices": [40]})
    monkeypatch.setattr("speedmap.inference.predictor.load_towers", lambda: towers)
    monkeypatch.setattr("speedmap.inference.predictor.load_cells", lambda: cells)
    monkeypatch.setattr("speedmap.inference.predictor.load_tiles", lambda: tiles)
    monkeypatch.setattr("speedmap.features.tower_features.theoretical_speed_mbps", lambda distances: 223.0)
    bundle = {
        "model": ConstantEstimator(133), "conformal": FixedInterval(),
        "secondary": {"upload_mbps": ConstantEstimator(31), "latency_ms": ConstantEstimator(18)},
    }
    return artifacts.save_model(bundle, "test_hybrid")


def test_saved_bundle_produces_valid_api_payload_and_shared_inputs(saved_model):
    predictor = Predictor("test_hybrid", saved_model.name)
    result = PredictionResponse.model_validate(predictor.predict(21.0285, 105.8542))
    assert result.source == "model" and result.confidence_level == 0.8
    assert result.download_mbps == 133 and result.upload_mbps == 31 and result.latency_ms == 18
    assert result.theory_mbps == 223 and result.local_effect_mbps == -90
    assert result.model_version == saved_model.name
    features = predictor.bundle["model"].last_features
    assert list(features.columns) == config.FEATURE_COLUMNS
    assert features["operators_1km"].iloc[0] == 2
    assert features["dist_nearest_tower_m"].iloc[0] == 0
    assert len(predictor.tower_list()) == 3


def test_unfinished_physics_fails_readiness(saved_model, monkeypatch):
    monkeypatch.setattr("speedmap.features.tower_features.theoretical_speed_mbps", lambda distances: np.nan)
    with pytest.raises(ValueError, match="non-finite"):
        Predictor("test_hybrid")


def test_incompatible_feature_contract_is_rejected(saved_model):
    import json

    metadata_file = saved_model / "metadata.json"
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    metadata["feature_columns"] = ["different_feature"]
    metadata_file.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="feature columns"):
        Predictor("test_hybrid")


def test_nonfinite_model_prediction_is_rejected_on_startup(saved_model, monkeypatch):
    monkeypatch.setattr(ConstantEstimator, "predict", lambda self, features: np.array([np.nan]))
    with pytest.raises(ValueError, match="finite"):
        Predictor("test_hybrid")
