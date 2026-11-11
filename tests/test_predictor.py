"""Exercise the saved-bundle adapter with real serialization and shared features."""
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
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
    tiles = pd.DataFrame({"quadkey": ["x"], "latitude": [21.029], "longitude": [105.855], "devices": [40], "tests": [12]})
    monkeypatch.setattr("speedmap.inference.predictor.load_cells", lambda: cells)
    monkeypatch.setattr("speedmap.inference.predictor.load_tiles", lambda: tiles)
    tower_file = tmp_path / "hanoi_towers.csv"
    towers.to_csv(tower_file, index=False)
    monkeypatch.setattr(config, "TOWERS_FILE", tower_file)
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
    area = predictor.predict_area(21.0285, 105.8542)
    assert area["area_download_mbps"] == 133 and area["area_radius_m"] == config.AREA_RADIUS_M
    assert area["area_points"] > 1


def test_unfinished_physics_fails_readiness(saved_model, monkeypatch):
    monkeypatch.setattr("speedmap.features.tower_features.theoretical_speed_mbps", lambda distances: np.nan)
    with pytest.raises(ValueError, match="non-finite"):
        Predictor("test_hybrid")


def test_official_model_api_exposes_area_estimate(saved_model, monkeypatch):
    monkeypatch.setenv("SPEEDMAP_MODEL_NAME", "test_hybrid")
    monkeypatch.delenv("SPEEDMAP_MODEL_RUN", raising=False)
    predictor = Predictor("test_hybrid", saved_model.name)
    with TestClient(create_app("actual", predictor)) as client:
        assert client.get("/api/health").json()["mode"] == "model"
        response = client.get("/api/predict?lat=21.0285&lon=105.8542")
        assert response.status_code == 200
        result = response.json()
        assert result["source"] == "model"
        assert result["area_radius_m"] == 500
        assert result["area_download_mbps"] == 133
        assert result["area_quality_level"] == config.quality_level(133)
        assert result["area_points"] > 1


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


def test_model_trained_on_different_towers_is_rejected(saved_model):
    config.TOWERS_FILE.write_text(config.TOWERS_FILE.read_text().replace("21.0285", "21.0295"))
    with pytest.raises(ValueError, match="towers data differs"):
        Predictor("test_hybrid")


def test_unversioned_model_is_rejected(saved_model):
    import json

    path = saved_model / "metadata.json"
    metadata = json.loads(path.read_text())
    metadata.pop("data_fingerprints")
    path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="provenance"):
        Predictor("test_hybrid")
