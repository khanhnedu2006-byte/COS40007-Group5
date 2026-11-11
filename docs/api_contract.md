# Regional API Contract (v0.3)

The app estimates typical download speed in a 1.5 km circle around an input coordinate. It combines mobile networks/operators and is not a live speed test. This replaces the previous point-level prediction response; clients must use the `area_*` fields.

## GET /api/health

```json
{"status":"ok","ready":true,"mode":"model","model_loaded":true,
 "model_version":"20261111-133102","tower_count":2398}
```

`mode` is `demo`, `data`, or `model`. Default `actual` resolves to `model` when a regional run is registered, otherwise `data`. Health also reports `tower_data_source`, available observation count/period and canonical data fingerprints. Demo can be ready with `model_loaded: false`. Failed model initialization returns `status: "unavailable"`, `ready: false`, and prediction/tower endpoints return 503. Model mode never falls back to demo.

## GET /api/boundary

Returns Hanoi's administrative boundary as a GeoJSON FeatureCollection, using the same local polygon as coordinate validation.

## GET /api/towers

Returns tower objects containing `tower_id` (integer or string), `latitude`, `longitude`, and `source`. OpenCelliD positions are estimated cell locations, not official tower sites. Demo tower sources are `simulated`.

## GET /api/predict?lat=21.0285&lon=105.8542

Example from the saved KNN regional run:

```json
{
  "latitude": 21.0285,
  "longitude": 105.8542,
  "area_radius_m": 1500,
  "area_download_mbps": 164.3,
  "area_quality_level": "Good",
  "area_points": 20,
  "area_ookla_tiles": 20,
  "area_grid_points": 0,
  "nearest_towers": [
    {"tower_id":1545,"latitude":21.029,"longitude":105.854,"distance_m":59,"source":"opencellid"},
    {"tower_id":1519,"latitude":21.027967,"longitude":105.853767,"distance_m":74,"source":"opencellid"},
    {"tower_id":1520,"latitude":21.0277,"longitude":105.8546,"distance_m":98,"source":"opencellid"}
  ],
  "source": "model",
  "model_name": "knn",
  "model_version": "20261111-133102"
}
```

- `area_download_mbps`: non-negative regional download estimate, rounded to one decimal. `area_quality_level` uses the same displayed value: Poor <15, Fair <100, Good <200, otherwise Excellent.
- `area_radius_m`: radius in metres, currently 1500; the map draws this circle.
- `area_points = area_ookla_tiles + area_grid_points`. Model mode samples measured tile centres in the circle, weighted by their test counts. Those counts define sampling support; the output pools model predictions rather than measured speeds.
- In model mode, with fewer than five measured tiles, add grid points spaced 300 m apart with unit weight, including when there are no measured tiles. Positive `area_grid_points` identifies sparse support. The full circle is sampled even when it crosses the city boundary; only its input centre must be inside Hanoi.
- `nearest_towers`: one to three locations ordered by distance from the input centre, in metres.
- `source`: `model`, `data`, or `demo`. Recorded-data mode uses `recorded` as its model name. Model names are `knn` or `random_forest`; demo uses `simulated`, version `demo-regional-v1`, simulated grid speeds, zero measured tiles, and explicit UI labels. Demo uses local tower locations when available, otherwise simulated towers; tower provenance is independent of simulated speed provenance.

Regional model/demo responses leave optional legacy point fields null. Recorded-data responses retain download/upload/latency, neighbour spread, and `data_support` fields for existing data clients. The UI presents the regional average where measured tiles exist; an empty recorded region is unavailable rather than filled with invented observations. Point-level neighbour spread is not a regional confidence interval.

Missing, malformed, non-finite, out-of-range or outside-polygon coordinates return 422. Prediction errors and unavailable models return 503 with a public string `detail`; internal errors are logged. Coordinates inside the bounding box but outside the polygon are rejected.

## Saved regional bundle

Location: `artifacts/models/regional/<run>/model.joblib` with adjacent `metadata.json` and parent `LATEST`.

```python
{"kind": "regional_baseline", "model": fitted_baseline,
 "model_name": "knn", "area_radius_m": 1500}
```

The estimator exposes `predict(features)` in Mbps. Metadata stores the ordered feature columns, settings, out-of-fold metrics, training period, input fingerprints, and scikit-learn version. KNN uses latitude/longitude; Random Forest uses `config.FEATURE_COLUMNS` except `theory_mbps`, with its fitted context imputer saved inside the model. The adapter rejects legacy hybrid/point bundles; train with `scripts/train_baselines.py`.

See [training.md](training.md) for evaluation and [data_contract.md](data_contract.md) for matching inputs. Keep saved models and processed data from the same run together; canonical data fingerprints are checked at startup. Older regional runs with equivalent input hashes in `provenance.input_sha256` are verified through those hashes; unversioned or mismatched inputs are rejected.
