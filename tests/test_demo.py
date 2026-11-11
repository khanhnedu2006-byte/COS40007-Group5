"""Dataset towers and simulated speeds must retain independent provenance."""
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.demo import DemoPredictor
from backend.main import create_app
from speedmap import config


@pytest.fixture
def tower_file(tmp_path):
    path = tmp_path / "hanoi_towers.csv"
    pd.DataFrame({
        "tower_id": [901, 902, 903],
        "latitude": [21.0285, 21.031, 21.04],
        "longitude": [105.8543, 105.8542, 105.86],
        "source": ["opencellid", "osm", "opencellid"],
        "samples": [25, 0, 10],
    }).to_csv(path, index=False)
    return path


def test_dataset_locations_ids_and_sources_are_used_without_modifying_file(tower_file):
    original = tower_file.read_bytes()
    predictor = DemoPredictor(tower_file)
    assert predictor.tower_data_source == "dataset"
    towers = predictor.tower_list()
    assert [tower["tower_id"] for tower in towers] == [901, 902, 903]
    assert towers[1]["source"] == "osm"
    result = predictor.predict(21.0285, 105.8542)
    assert result["source"] == "demo" and result["model_name"] == "simulated"
    assert result["area_radius_m"] == 1500
    assert [tower["tower_id"] for tower in result["nearest_towers"]] == [901, 902, 903]
    # 0.0001 degrees of longitude at Hanoi's latitude is approximately 10.4 metres.
    assert result["nearest_towers"][0]["distance_m"] == pytest.approx(10, abs=1)
    assert result["nearest_towers"][0]["source"] == "opencellid"
    assert tower_file.read_bytes() == original


def test_missing_file_keeps_data_free_demo_available(tmp_path):
    path = tmp_path / "missing.csv"
    predictor = DemoPredictor(path)
    assert predictor.tower_data_source == "simulated"
    assert all(tower["source"] == "simulated" for tower in predictor.tower_list())
    assert predictor.predict(21.0285, 105.8542)["area_download_mbps"] == 144.0
    assert not path.exists()


def test_health_identifies_real_locations_without_claiming_model_is_loaded(tower_file, monkeypatch):
    monkeypatch.setattr(config, "TOWERS_FILE", tower_file)
    with TestClient(create_app("demo")) as client:
        health = client.get("/api/health").json()
        assert health["ready"] and health["mode"] == "demo"
        assert health["tower_data_source"] == "dataset" and health["tower_count"] == 3
        assert not health["model_loaded"]
        assert client.get("/api/towers").json()[0]["tower_id"] == 901
        result = client.get("/api/predict?lat=21.0285&lon=105.8542").json()
        assert result["source"] == "demo"
        assert result["nearest_towers"][0]["source"] == "opencellid"


@pytest.mark.parametrize("problem", ["empty", "columns", "missing_id", "duplicate_id", "nan", "infinite", "range"])
def test_invalid_dataset_is_rejected_instead_of_silently_using_fake_towers(tower_file, problem):
    towers = pd.read_csv(tower_file)
    if problem == "empty":
        towers = towers.iloc[:0]
    elif problem == "columns":
        towers = towers.drop(columns="longitude")
    elif problem == "missing_id":
        towers.loc[0, "tower_id"] = np.nan
    elif problem == "duplicate_id":
        towers.loc[1, "tower_id"] = towers.loc[0, "tower_id"]
    else:
        towers.loc[0, "latitude"] = {"nan": np.nan, "infinite": np.inf, "range": 100}[problem]
    towers.to_csv(tower_file, index=False)
    with pytest.raises(ValueError):
        DemoPredictor(tower_file)


def test_missing_source_is_labelled_as_estimated(tower_file):
    towers = pd.read_csv(tower_file).drop(columns="source")
    towers.to_csv(tower_file, index=False)
    assert all(tower["source"] == "estimated" for tower in DemoPredictor(tower_file).tower_list())
