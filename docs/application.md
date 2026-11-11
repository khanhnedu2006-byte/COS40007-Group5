# Application development and model handoff

The frontend and backend can be developed while the data/model work continues. The default `actual` service selects recorded-data estimates until a hybrid bundle is registered. Data mode reads current Ookla tiles and towers; demo mode explicitly uses simulated speeds. Recorded estimates are historical area performance, and their nearby measured range is not a calibrated confidence interval.

## Local run

On Windows, double-click `demo.bat` for simulated predictions or `start.bat` for current recorded data or an available saved-model bundle. `scripts/launch.cmd` prefers this computer's Python (`py -3`, `python` or `python3`) and calls the shared `scripts/launch.py` manager. A working `.venv` interpreter is a fallback when those commands are unavailable. The manager validates the environment's original Python version, base interpreter, architecture and project location. A broken or incompatible environment is preserved under `.venv.backup-<timestamp>/`, then recreated with the selected interpreter.

Setup ensures pip is present and upgrades pip, setuptools and wheel before installing `requirements-app.txt` (demo/data) or `requirements-model.txt` (real model), then installs the shared package. It runs `npm ci` when needed. Backend cache keys include the Python runtime and absolute project location; frontend keys also include Node and the operating system/architecture. Copied cache files therefore cannot skip setup on a different project location or runtime.

The launcher starts Python and Node directly, waits for `/api/health` through both ports, checks the requested prediction mode and opens the browser. Press Enter in its console to stop its own services. Ready services can be reused, but a running demo backend cannot be reused as model mode. Port conflicts and failed model readiness produce errors; logs are written to `.run/`. The launchers require Python and Node/npm to be installed first. Model files and completed shared physics still come from the model team.

For a startup/cleanup smoke check without opening a browser, run `python scripts/launch.py demo --smoke-test`. The normal data-backed check is `python scripts/launch.py actual --smoke-test`. A real-model check is `python scripts/launch.py model --smoke-test` once artifacts are available. The checks use the normal local ports and leave reused services running.

### Manual startup

Use 64-bit Python 3.11+ (including 3.14.7) and Node 22.13+ (the application lint tool requires a recent Node version). Application CI covers Python 3.11 on Linux and 3.14.7 on Windows. The separate TensorFlow training workflow retains Python 3.11; a real model must still have compatible estimator dependencies.
From the repository root, activate your virtual environment, then:

```powershell
python -m pip install -r requirements-dev.txt
python -m pip install -e . --no-deps
python -m uvicorn backend.main:app --reload
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Visit http://127.0.0.1:5173. Vite proxies `/api` to `127.0.0.1:8000`. Both development servers bind locally. Port 5173 is strict, so an existing process gives a clear error instead of silently switching ports. `/api/health` reports readiness and operating mode; `/docs` exposes the typed API.

The default Signal focus basemap uses Stadia Maps' Alidade Smooth raster style, with fewer points of interest and muted roads so prediction results stand out. The optional Detailed streets style uses standard OpenStreetMap tiles. Both styles require internet access. Fonts load separately from Google Fonts, with system fonts as a fallback. If tiles fail, the application shows a message and the local prediction API remains usable. Neighbourhood shortcuts and coordinate entry also provide alternatives to clicking the map. Location access is requested only when the user clicks the location button.

Tower markers and the three nearest tower connections are hidden by default. Enable them under Layers when inspecting the infrastructure behind a prediction. The selected location is coloured by its download-quality category; these colours represent predicted mobile speed, not a measured radio signal in dBm. The demo label remains visible on simulated results.

### Canonical data inputs

All active runtime and training paths use `speedmap.config`: `data/interim/hanoi_towers.csv`, `data/processed/hanoi_tiles.csv` and `data/processed/hanoi_train.csv`. Current counts are 2,398 towers, 5,212 pooled tiles and 24,679 tile-quarter records through 2026-3. Copy these local data folders when sharing the project; restart services after updates.

`DataPredictor` uses up to five nearest recorded tiles, weighted by distance and square root of test count. At a recorded tile centre it returns that tile's observed download, upload and latency exactly. Between tiles it averages log speeds and latency. The nearby measured range shows the neighbouring download minimum and maximum; it has no confidence claim. Physics and local adjustment are absent in this mode. Missing or invalid data leaves the service unavailable.

`model.py` defaults to the canonical training table. `python scripts/sync_ci_data.py` copies it to the committed CI snapshot and records a content manifest. CI explicitly selects that snapshot and verifies its hash; there is no implicit fallback to older data. The feature pipeline refreshes it automatically. Earlier Irish traces and `ml/` prototypes are not active data sources.

### Demo tower data

`DemoPredictor` reads `data/interim/hanoi_towers.csv` at startup using the shared tower loader. Required columns are `tower_id`, `latitude` and `longitude`; `source` is preserved when present and otherwise labelled `estimated`. IDs must be present and unique, and coordinates must be finite and within valid latitude/longitude ranges. An invalid existing table makes the service unavailable with a logged error, rather than silently replacing user data with synthetic towers.

The full processed table is retained, including the data team's near-border buffer, so points inside Hanoi can use the true nearest cell locations across the boundary. Click eligibility remains restricted to Hanoi. API tower responses expose the IDs, coordinates and sources, and nearest-tower distances use the same loaded table. Speed values and ranges remain simulated in demo mode.

When the file is absent, generated towers keep the demo usable without a dataset. `/api/health` reports `tower_data_source` as `dataset` or `simulated`; the banner, footer, layers and result panel distinguish tower provenance from prediction mode. Restart the backend or demo launcher after changing the CSV. Copy this CSV separately when sharing the data-enabled demo with another computer; `data/interim/` is intentionally excluded from Git.

Stadia Maps permits keyless browser development on `localhost` and `127.0.0.1`, subject to development rate limits. Before public hosting, configure its domain authentication or choose another basemap provider; see the [Stadia authentication guide](https://docs.stadiamaps.com/authentication/). The original OpenStreetMap style remains available under Layers. Basemap URLs and attribution are defined in `frontend/src/basemaps.js`.

The explorer is limited to Hanoi: panning is bounded to the city envelope, zoom cannot go below level 10, and neighbouring provinces are muted outside the administrative polygon. Coordinate entry, map clicks and browser location are checked against that polygon before requesting a prediction or moving the view; the backend independently repeats validation. Browser location outside Hanoi displays a message and leaves the map in Hanoi.

The Leaflet scene is isolated from form and panel state so typing cannot redraw the towers. Tower groups are clustered at every zoom level and only mounted near the viewport. Tile requests are restricted to the Hanoi envelope, with a small buffer and no intermediate zoom requests. Programmatic location changes are immediate; map filters and backdrop blur are avoided to reduce rendering work.

## Switch to the team's trained model

The model team supplies:

- `artifacts/models/hybrid/<run>/model.joblib` and `metadata.json`, plus `LATEST` if no run is explicitly selected.
- `data/interim/hanoi_towers.csv` with at least `tower_id`, `latitude`, `longitude`.
- The completed shared physics functions used by `speedmap.features.tower_features`.
- Any extra runtime dependencies required by the saved estimators, such as `xgboost`, installed in the same Python environment.

The bundle interface is documented in [api_contract.md](api_contract.md). The adapter loads it once at startup, uses the shared feature builder and the bundle's quarter index, and smoke-tests a prediction at the city centre. Missing artifacts, incompatible feature columns, unfinished physics or invalid outputs keep the prediction service unavailable. The backend logs the cause; the frontend shows a service error. It never changes to demo mode automatically.

In PowerShell, before starting the backend:

```powershell
$env:SPEEDMAP_MODE = 'model'
$env:SPEEDMAP_MODEL_NAME = 'hybrid'
$env:SPEEDMAP_MODEL_RUN = '20261020-101500' # Replace with the actual approved run ID.
python -m uvicorn backend.main:app --reload
```

Pin the agreed run explicitly. Without `SPEEDMAP_MODEL_RUN`, the existing registry's `LATEST` file is used; that file marks the latest saved run, not an independently approved champion. The shared artifact writer records canonical data fingerprints. Inference verifies them and rejects changed data or unversioned bundles. The model owner must fit on those same inputs before saving; champion promotion remains a team decision. Restart the backend after changing the artifact or environment settings.

To return to demo mode, set `$env:SPEEDMAP_MODE = 'demo'` and restart.

| Variable | Default | Purpose |
| --- | --- | --- |
| `SPEEDMAP_MODE` | `actual` | `actual` selects model if registered, otherwise data. Explicit `data`, `demo` or strict `model` also supported. |
| `SPEEDMAP_MODEL_NAME` | `hybrid` | Saved model directory. |
| `SPEEDMAP_MODEL_RUN` | unset | Specific run; otherwise registry `LATEST`. |
| `SPEEDMAP_CORS_ORIGINS` | localhost and 127.0.0.1 on port 5173 | Comma-separated allowed development origins. |

## Application checks

From the root:

```powershell
python -m pip install -r requirements-dev.txt
python -m ruff check backend src/speedmap/inference src/speedmap/data/catalog.py src/speedmap/runtime.py scripts/launch.py scripts/sync_ci_data.py model.py tests/test_current_data.py tests/test_api.py tests/test_demo.py tests/test_predictor.py tests/test_launcher.py
python -m pytest tests/test_api.py tests/test_demo.py tests/test_predictor.py tests/test_launcher.py tests/test_boundary.py tests/test_features.py tests/test_artifacts.py tests/test_current_data.py -q
```

From `frontend/`:

```powershell
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
```

Browser tests start local servers automatically unless they are already running. Use demo mode when reusing a running backend. Tests cover desktop and mobile, neighbourhood predictions, coordinate validation, direct map clicks, layers, the project dialog, reconnection, and changing selections while an earlier request is pending. Tests block third-party fonts and map requests so external outages cannot fail the application checks.

The saved-model adapter is tested using serialized test estimators and real shared spatial features. These tests establish the interface, not the eventual model's prediction accuracy. The full repository test suite still includes the model owner's unfinished physics tests; application CI deliberately runs the checks that can pass before that work is complete. Add completed model checks to the team pipeline when ready.

## Docker and CI

`docker compose up --build` builds the FastAPI backend and React frontend, serves the frontend through Nginx at http://127.0.0.1:8080, and proxies `/api` to the backend. Both services have health checks; only local interfaces are published. The default stack uses `actual` mode and mounts `data/interim/`, `data/processed/` and `artifacts/models/` read-only. Set `SPEEDMAP_MODE=demo` for a data-free demo; application CI does this explicitly. Stop it with `docker compose down`.

The backend installs the shared package in editable form inside the image because current shared settings resolve data paths relative to `src/speedmap/config.py`. Raw data and model artifacts are excluded from the build context. The image installs `requirements-model.txt`, including XGBoost. Add any further estimator dependencies required by the eventual bundle.

`.github/workflows/application.yml` runs Python lint, application/interface tests, notebook-output checks, frontend lint/build, desktop/mobile browser flows, and a Docker Compose smoke test. It is separate from the original TensorFlow training workflow. No deployment or public hosting is configured yet.

Requests and predictions are logged as JSON through Uvicorn, including endpoint, status, duration, clicked coordinates and model version. Model monitoring, quarterly back-tests and retraining belong to the model owner's workflow; the service exposes the information needed to integrate them later.
