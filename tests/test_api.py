"""Application tests run without raw datasets or a trained model."""
import pytest
from fastapi.testclient import TestClient

from backend.main import create_app


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app("demo")) as service:
        yield service


def test_demo_health_identifies_fixture_data(client):
    status = client.get("/api/health").json()
    assert status["ready"] and status["mode"] == "demo"
    assert not status["model_loaded"]
    towers = client.get("/api/towers").json()
    assert len(towers) == status["tower_count"] > 3
    assert status["tower_data_source"] in {"dataset", "simulated"}


@pytest.mark.parametrize("lat,lon", [(21.0285, 105.8542), (21.0589, 105.8233), (20.9719, 105.7772)])
def test_inside_points_return_consistent_complete_predictions(client, lat, lon):
    response = client.get("/api/predict", params={"lat": lat, "lon": lon})
    assert response.status_code == 200
    result = response.json()
    assert result == client.get("/api/predict", params={"lat": lat, "lon": lon}).json()
    assert result["source"] == "demo" and result["model_name"] == "simulated"
    assert result["area_download_mbps"] >= 0
    assert result["area_radius_m"] == 500
    assert result["area_points"] == result["area_grid_points"] > 1
    assert result["area_ookla_tiles"] == 0
    assert all(result.get(key) is None for key in ("download_mbps", "upload_mbps", "latency_ms", "download_low", "theory_mbps"))
    distances = [tower["distance_m"] for tower in result["nearest_towers"]]
    assert len(distances) == 3 and distances == sorted(distances)
    from speedmap import config
    assert result["area_quality_level"] == config.quality_level(result["area_download_mbps"])


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


def test_map_receives_prediction_boundary(client):
    geo = client.get("/api/boundary").json()
    assert geo["type"] == "FeatureCollection"
    assert geo["features"][0]["geometry"]["type"] in {"Polygon", "MultiPolygon"}


@pytest.mark.parametrize("lat,lon", [(21.12, 105.82), (20.85, 105.8), (21.03, 105.6)])
def test_outer_hanoi_is_not_supported_for_predictions(client, lat, lon):
    from speedmap import config

    assert config.inside_hanoi(lat, lon)
    response = client.get("/api/predict", params={"lat": lat, "lon": lon})
    assert response.status_code == 422
    assert "central Hanoi" in response.json()["detail"]


def test_prediction_boundary_contains_all_location_shortcuts(client):
    from speedmap.inference.coverage import supports_location

    for lat, lon in [(21.0285, 105.8542), (21.0589, 105.8233), (21.0362, 105.7906), (20.9719, 105.7772)]:
        assert supports_location(lat, lon)
    ring = client.get("/api/boundary").json()["features"][0]["geometry"]["coordinates"][0]
    # The previous fixed rectangle cut through the western and eastern clusters.
    assert min(point[0] for point in ring) < 105.75
    assert max(point[0] for point in ring) > 105.92


@pytest.mark.parametrize("lat,lon", [(21.02, 105.74), (21.03, 105.92), (20.92, 105.85), (20.96, 105.825)])
def test_supported_urban_clusters_are_included(client, lat, lon):
    assert client.get("/api/predict", params={"lat": lat, "lon": lon}).status_code == 200


def test_prediction_boundary_has_no_interior_holes(client):
    geometry = client.get("/api/boundary").json()["features"][0]["geometry"]
    assert len(geometry["coordinates"]) == 1
    # This location previously fell in an interior gap near West Lake.
    response = client.get("/api/predict?lat=21.05&lon=105.82")
    assert response.status_code == 200


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
