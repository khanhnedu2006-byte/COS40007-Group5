# Application development and model handoff

The frontend and backend can be developed while the data/model work continues. The default service uses deterministic demo fixtures, with no dependency on a trained artifact. Simulated results are never represented as measured performance or calibrated intervals.

## Local run

Use Python 3.11+ and Node 22.13+ (the application lint tool requires a recent Node version).
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

The street tiles come from OpenStreetMap and fonts from Google Fonts; both require internet access. System fonts provide a fallback. If tiles fail, the application shows a message and the local prediction API remains usable. Neighbourhood shortcuts and coordinate entry also provide alternatives to clicking the map. Location access is requested only when the user clicks the location button.

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

Pin the agreed run explicitly. Without `SPEEDMAP_MODEL_RUN`, the existing registry's `LATEST` file is used; that file marks the latest saved run, not an independently approved champion. Champion promotion and artifact/data compatibility remain a coordination point with the model owner. Restart the backend after changing the artifact or environment settings.

To return to demo mode, set `$env:SPEEDMAP_MODE = 'demo'` and restart.

| Variable | Default | Purpose |
| --- | --- | --- |
| `SPEEDMAP_MODE` | `demo` | Explicit `demo` or `model` service. |
| `SPEEDMAP_MODEL_NAME` | `hybrid` | Saved model directory. |
| `SPEEDMAP_MODEL_RUN` | unset | Specific run; otherwise registry `LATEST`. |
| `SPEEDMAP_CORS_ORIGINS` | localhost and 127.0.0.1 on port 5173 | Comma-separated allowed development origins. |

## Application checks

From the root:

```powershell
python -m ruff check backend src/speedmap/inference tests/test_api.py tests/test_predictor.py
python -m pytest tests/test_api.py tests/test_predictor.py tests/test_boundary.py tests/test_features.py tests/test_artifacts.py -q
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

`docker compose up --build` builds the FastAPI backend and React frontend, serves the frontend through Nginx at http://127.0.0.1:8080, and proxies `/api` to the backend. Both services have health checks; only local interfaces are published. The default stack uses demo mode. Stop it with `docker compose down`.

The backend installs the shared package in editable form inside the image because current shared settings resolve data paths relative to `src/speedmap/config.py`. Raw data and model artifacts are excluded from the build context. When integrating a real model into Docker, add its estimator dependencies and read-only mounts at `/app/artifacts/models` and `/app/data/interim`; agree those details once the actual bundle is available.

`.github/workflows/application.yml` runs Python lint, application/interface tests, notebook-output checks, frontend lint/build, desktop/mobile browser flows, and a Docker Compose smoke test. It is separate from the original TensorFlow training workflow. No deployment or public hosting is configured yet.

Requests and predictions are logged as JSON through Uvicorn, including endpoint, status, duration, clicked coordinates and model version. Model monitoring, quarterly back-tests and retraining belong to the model owner's workflow; the service exposes the information needed to integrate them later.
