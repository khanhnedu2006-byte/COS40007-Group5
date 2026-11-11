"""Current input routing, recorded estimates and stale-artifact protection."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from speedmap import config
from speedmap.data.catalog import (
    file_digest,
    load_ci_training_table,
    sync_ci_snapshot,
)
from speedmap.inference.data_predictor import DataPredictor
from speedmap.runtime import resolve_mode


@pytest.fixture
def current_data(tmp_path, monkeypatch):
    towers = tmp_path / "towers.csv"
    pd.DataFrame({"tower_id": ["NEW-A", "NEW-B", "NEW-C"],
                  "latitude": [21.0285, 21.03, 21.04],
                  "longitude": [105.8542, 105.85, 105.86],
                  "source": ["opencellid", "osm", "opencellid"]}).to_csv(towers, index=False)
    rows = pd.DataFrame({"quadkey": ["001", "002", "003"],
                         "latitude": [21.0285, 21.03, 21.04],
                         "longitude": [105.8542, 105.85, 105.86],
                         "download_mbps": [75., 150., 225.], "upload_mbps": [12., 24., 36.],
                         "latency_ms": [18., 25., 40.], "tests": [4, 9, 16],
                         "first_quarter": ["2025-4"] * 3, "last_quarter": ["2026-3"] * 3})
    tiles = tmp_path / "tiles.csv"
    rows.to_csv(tiles, index=False)
    training = rows.assign(quarter="2026-3", quarter_index=8106,
                           dist_nearest_tower_m=0, towers_500m=2, towers_1km=3,
                           theory_mbps=np.nan, sample_weight=2, block_id=1)
    for column in config.FEATURE_COLUMNS:
        if column not in training:
            training[column] = np.nan if column in config.OPTIONAL_FEATURES else 0
    train = tmp_path / "train.csv"
    training.to_csv(train, index=False)
    for name, path in [("TOWERS_FILE", towers), ("TILES_FILE", tiles), ("TRAIN_FILE", train)]:
        monkeypatch.setattr(config, name, path)
    monkeypatch.setattr(config, "ARTIFACTS_MODELS", tmp_path / "models")
    return rows


def test_actual_start_uses_recorded_measurements_and_current_towers(current_data, monkeypatch):
    monkeypatch.delenv("SPEEDMAP_MODEL_RUN", raising=False)
    with TestClient(create_app("actual")) as client:
        health = client.get("/api/health").json()
        assert health["ready"] and health["mode"] == "data"
        assert not health["model_loaded"]
        assert health["observation_count"] == 3 and health["data_period"] == "2026-3"
        assert health["data_fingerprints"]["towers"] == file_digest(config.TOWERS_FILE)
        result = client.get("/api/predict?lat=21.0285&lon=105.8542").json()
        assert result["download_mbps"] == 75
        assert result["upload_mbps"] == 12 and result["latency_ms"] == 18
        assert result["source"] == "data" and result["interval_kind"] == "neighbour_spread"
        assert result["confidence_level"] is None and result["theory_mbps"] is None
        assert result["local_effect_mbps"] is None
        assert result["nearest_towers"][0]["tower_id"] == "NEW-A"
        assert result["nearest_towers"][0]["distance_m"] == 0
        assert result["data_support"]["tests"] == 29
        assert client.get("/api/predict?lat=10.7769&lon=106.7009").status_code == 422


def test_interpolation_uses_only_nearby_observations(current_data):
    result = DataPredictor().predict(21.032, 105.853)
    assert 75 < result["download_mbps"] < 225
    assert 12 < result["upload_mbps"] < 36
    assert result["download_low"] == 75 and result["download_high"] == 225


@pytest.mark.parametrize("name", ["TOWERS_FILE", "TILES_FILE"])
def test_missing_actual_input_never_produces_demo(current_data, name):
    getattr(config, name).unlink()
    with TestClient(create_app("data")) as client:
        assert not client.get("/api/health").json()["ready"]
        assert client.get("/api/predict?lat=21.0285&lon=105.8542").status_code == 503


def test_actual_selects_existing_model_without_masking_broken_bundles(tmp_path):
    assert resolve_mode("actual", tmp_path) == "data"
    directory = tmp_path / "hybrid"
    directory.mkdir()
    (directory / "LATEST").write_text("broken-run")
    assert resolve_mode("actual", tmp_path) == "model"
    assert resolve_mode("actual", tmp_path, run_id="pinned-run") == "model"
    assert resolve_mode("data", tmp_path) == "data"


def test_invalid_registered_model_never_changes_to_recorded_data(current_data):
    directory = config.ARTIFACTS_MODELS / "hybrid"
    directory.mkdir(parents=True)
    (directory / "LATEST").write_text("missing-run")
    with TestClient(create_app("actual")) as client:
        health = client.get("/api/health").json()
        assert health["mode"] == "model" and not health["ready"]
        assert client.get("/api/predict?lat=21.0285&lon=105.8542").status_code == 503


def test_ci_snapshot_is_exact_and_rejects_stale_data(current_data, tmp_path):
    destination = tmp_path / "ci.csv"
    manifest = sync_ci_snapshot(destination)
    assert destination.read_bytes() == config.TRAIN_FILE.read_bytes()
    assert manifest["rows"] == len(current_data)
    table, _ = load_ci_training_table(destination)
    assert table["quadkey"].tolist() == ["001", "002", "003"]
    config.TRAIN_FILE.write_text(config.TRAIN_FILE.read_text().replace("75.0", "85.0"))
    with pytest.raises(ValueError, match="older dataset"):
        load_ci_training_table(destination)
    sync_ci_snapshot(destination)
    destination.write_text(destination.read_text().replace("85.0", "95.0"))
    with pytest.raises(ValueError, match="manifest"):
        load_ci_training_table(destination)


def test_digest_is_portable_across_git_line_endings(tmp_path):
    path = tmp_path / "table.csv"
    path.write_bytes(b"a,b\n1,2\n")
    digest = file_digest(path)
    path.write_bytes(b"a,b\r\n1,2\r\n")
    assert file_digest(path) == digest


def test_model_data_check_defaults_to_canonical_table(current_data, capsys, monkeypatch):
    import model

    monkeypatch.setattr(model, "DATA_FILE", config.TRAIN_FILE)
    model.main(["--check-data"])
    result = json.loads(capsys.readouterr().out)
    assert Path(result["source"]) == config.TRAIN_FILE
    assert result["rows"] == 3 and result["last_quarter"] == "2026-3"
