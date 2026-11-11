"""Application tests run without raw datasets or a trained model."""
import pytest
from fastapi.testclient import TestClient

from backend.demo import DemoPredictor
from backend.main import create_app


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    predictor = DemoPredictor(tmp_path_factory.mktemp("demo-fixtures") / "missing.csv")
    with TestClient(create_app("demo", predictor)) as service:
        yield service


def test_demo_health_identifies_fixture_data(client):
    status = client.get("/api/health").json()
    assert status["ready"] and status["mode"] == "demo"
    assert not status["model_loaded"]
    assert status["tower_data_source"] == "simulated"
    towers = client.get("/api/towers").json()
    assert len(towers) == status["tower_count"] > 3
    assert all(tower["source"] == "simulated" for tower in towers)


@pytest.mark.parametrize("lat,lon", [(21.0285, 105.8542), (21.0589, 105.8233), (20.9719, 105.7772)])
def test_inside_points_return_consistent_complete_predictions(client, lat, lon):
    response = client.get("/api/predict", params={"lat": lat, "lon": lon})
    assert response.status_code == 200
    result = response.json()
    assert result == client.get("/api/predict", params={"lat": lat, "lon": lon}).json()
    assert result["source"] == "demo" and result["interval_kind"] == "illustrative"
    assert result["confidence_level"] is None
    assert result["area_radius_m"] == 1500
    assert result["area_download_mbps"] is None
    assert result["download_low"] <= result["download_mbps"] <= result["download_high"]
    distances = [tower["distance_m"] for tower in result["nearest_towers"]]
    assert len(distances) == 3 and distances == sorted(distances)
    assert result["download_mbps"] == pytest.approx(result["theory_mbps"] + result["local_effect_mbps"])


@pytest.mark.parametrize("lat,lon", [(10.7769, 106.7009), (21.3089, 105.6049)])
def test_outside_polygon_is_rejected_even_inside_old_bounding_box(client, lat, lon):
    response = client.get("/api/predict", params={"lat": lat, "lon": lon})
    assert response.status_code == 422
    assert "outside Hanoi" in response.json()["detail"]


@pytest.mark.parametrize("params", [
    {}, {"lat": "text", "lon": 105}, {"lat": 91, "lon": 105},
    {"lat": 21, "lon": 181}, {"lat": "nan", "lon": 105}, {"lat": 21, "lon": "inf"},
])
def test_invalid_coordinates_are_validation_errors(client, params):
    assert client.get("/api/predict", params=params).status_code == 422


def test_map_receives_administrative_boundary(client):
    geo = client.get("/api/boundary").json()
    assert geo["type"] == "FeatureCollection"
    assert geo["features"][0]["geometry"]["type"] in {"Polygon", "MultiPolygon"}


def test_unavailable_model_never_falls_back_to_demo(monkeypatch):
    def missing(*args):
        raise FileNotFoundError("No model yet")

    monkeypatch.setattr("speedmap.inference.predictor.load_model", missing)
    with TestClient(create_app("model")) as client:
        status = client.get("/api/health").json()
        assert not status["ready"] and status["mode"] == "model"
        assert client.get("/api/towers").status_code == 503
        assert client.get("/api/predict?lat=21.0285&lon=105.8542").status_code == 503


def test_predictor_failure_is_recoverable():
    class BrokenPredictor:
        def predict(self, lat, lon):
            raise RuntimeError("private implementation detail")

    with TestClient(create_app("demo", BrokenPredictor())) as client:
        response = client.get("/api/predict?lat=21.0285&lon=105.8542")
        assert response.status_code == 503
        assert "private implementation detail" not in response.text


def test_allowed_local_origin_can_call_api(client):
    response = client.get("/api/health", headers={"Origin": "http://127.0.0.1:5173"})
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_invalid_mode_fails_explicitly():
    with pytest.raises(ValueError, match="SPEEDMAP_MODE"):
        create_app("automatic")
