# API Contract

Produced by Person 3 (backend), using the bundle saved by Person 2 (notebook 06).

## GET /api/health
```json
{"status": "ok", "ready": true, "mode": "demo", "model_loaded": false,
 "model_version": "demo-v1", "tower_count": 2398, "tower_data_source": "dataset"}
```

`ready` means predictions can be served. `model_loaded` is false in demo mode.
`tower_count` depends on the loaded file. `tower_data_source` distinguishes `"dataset"` locations from the `"simulated"` fallback, independently of prediction mode; it is `null` when the service is unavailable.
Model startup failures return `status: "unavailable"`, `ready: false` and prediction/tower endpoints return 503. Model mode never falls back to simulated data.

## GET /api/boundary
Returns the Hanoi administrative boundary as a GeoJSON FeatureCollection, using the same local file as coordinate validation.

## GET /api/towers
```json
[{"tower_id": 1, "latitude": 21.0285, "longitude": 105.8542}, ...]
```

## GET /api/predict?lat=21.0285&lon=105.8542
```json
{
  "latitude": 21.0285, "longitude": 105.8542,
  "download_mbps": 133.0, "download_low": 95.0, "download_high": 170.0,
  "upload_mbps": 31.0, "latency_ms": 18.0,
  "quality_level": "Good",
  "theory_mbps": 223.0, "local_effect_mbps": -90.0,
  "nearest_towers": [
    {"tower_id": 1, "latitude": 21.03, "longitude": 105.85, "distance_m": 400, "source": "opencellid"}
  ],
  "source": "model", "model_version": "20261020-101500",
  "interval_kind": "conformal", "confidence_level": 0.8
}
```
Errors: `422` if the point is outside Hanoi; `503` if no model is saved yet.

Missing, malformed, non-finite and out-of-range coordinates also return 422 using FastAPI's standard validation response. Prediction errors use a string `detail`. Coordinates inside the old bounding box but outside the administrative polygon are rejected.

In demo mode, prediction `source` is `"demo"`, `interval_kind` is `"illustrative"`, and `confidence_level` is `null`. When `data/interim/hanoi_towers.csv` exists, tower IDs, coordinates and sources (such as `"opencellid"` or `"osm"`) come from the dataset, and distances are computed from those positions. When the file is absent, tower IDs are strings such as `"DEMO-001"` with `source: "simulated"`. Tower IDs may be integers or strings in either mode. Tower provenance does not change the simulated nature of demo speeds and ranges.

## Saved model bundle (`artifacts/models/hybrid/<run>/model.joblib`)
```python
{"model": HybridModel, "conformal": ConformalInterval,
 "secondary": {"upload_mbps": XGBRegressor, "latency_ms": XGBRegressor}}
```

The inference adapter calls `model.predict(features)`, `conformal.interval(predictions)` (a `(low, high)` pair), and each secondary estimator's `predict(features)`. Features use exactly `config.FEATURE_COLUMNS`, built by `PointFeaturizer` from hanoi_towers.csv, hanoi_cells.csv, hanoi_tiles.csv and the context grid (no `quarter_index`; the model is retrained each quarter instead). Context features may be NaN; all other features must be finite. All outputs must be finite and non-negative, with the download estimate inside its interval. Shared physics must be implemented before model mode can become ready.

## Area estimate (1.5 km radius) — decided 9 Nov 2026
`Predictor.predict_area(lat, lon)` returns the typical download speed of the area around the click:
```json
{"area_radius_m": 1500, "area_download_mbps": 118.4, "area_quality_level": "Good",
 "area_points": 41, "area_ookla_tiles": 41}
```
Points = Ookla tiles within 1.5 km weighted by tests (grid points every 300 m are added where there are fewer than 5 tiles).
Spatial CV: 77.8% correct quality level for 1.5 km areas (single tiles: 62–71%). The UI should draw the 1.5 km circle and
word the result as "the area around this point", not as the exact speed at the point.
