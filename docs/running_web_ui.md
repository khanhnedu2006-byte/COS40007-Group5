# Run the Web UI

Hanoi Signal has a FastAPI backend on port **8000** and a React/Vite frontend on **5173**. Start from the repository root. Use 64-bit Python 3.11+ and Node.js 22.13+ in the Node 22 line, or Node.js 24+. The launcher checks these prerequisites.

## Choose the operating mode

The mode controls where the displayed speed comes from. Set `SPEEDMAP_MODE` before starting the API, or pass the mode as the launcher's argument. These values are available:

- **`demo` — simulated speeds.** Use this to explore the interface without downloaded observations or a trained model. Speeds are generated for demonstration and are not measurements or model predictions. The app uses `data/interim/hanoi_towers.csv` for tower locations if it exists; otherwise it generates simulated locations. An invalid existing tower file leaves the predictor unavailable rather than being replaced silently.
- **`data` — recorded observations.** Use this to inspect Ookla measurements without training a model. The regional value is a test-weighted average of observed tiles within 500 m; a region without observations is unavailable. Prepare `data/processed/hanoi_tiles.csv` and `data/interim/hanoi_towers.csv` as described in [Fetch and prepare data](fetching_data.md). Recorded speeds describe the collected period, not a live measurement.
- **`model` — trained predictions.** Use this to serve a saved regional model and estimate typical performance around a location. Requires a trained model bundle, matching processed tiles, towers and cells, reference data, and compatible model dependencies; follow [the training guide](training.md). The default output radius is 500 m, though a pinned run can use its saved radius. Missing, incompatible, or stale inputs leave the service unavailable.
- **`actual` — automatic selection (default).** Use this when you want the app to choose between the real-data modes at startup. If `SPEEDMAP_MODEL_RUN` is set or the selected model has a `LATEST` file, it chooses `model`; otherwise it chooses `data`. It checks whether a run is selected, not whether that run can load successfully. If the chosen model is broken, the predictor remains unavailable and does not fall back to data or demo. If no model is selected, `data` still requires its prepared inputs.

`SPEEDMAP_MODEL_NAME` selects the model directory and defaults to `regional`; `SPEEDMAP_MODEL_RUN` pins a run within that directory. Without a pin, model mode reads its `LATEST` file. Check `/api/health` after startup: `mode` shows the resolved mode (`demo`, `data`, or `model`), `ready` indicates whether it loaded, and `model_loaded` indicates a loaded model. An unavailable predictor causes prediction requests to return HTTP 503; check the backend logs for the cause.

None of these modes provides a live speed test or an operator-specific result.

## Option A: launch both services together

On Windows, double-click:

- `start.bat` for `actual` mode.
- `demo.bat` for simulated speeds.

The launchers create/check the local environment, install dependencies when needed, start both services, verify readiness and open the browser. First setup needs internet access. An incompatible copied environment is preserved as a backup and recreated.

Alternatively, after installing the package in an environment as shown in Option B, run this from a terminal on any supported platform:

```sh
python -m speedmap.cli.launch actual
```

Replace `actual` with `data`, `model`, or `demo` to select a mode explicitly. Use the interpreter in the environment where the package is installed. The Windows batch files can bootstrap the environment before the package is installed.

Keep the launcher console open. Press **Enter** there to stop services it started. It can reuse ready services of the same resolved mode; stop existing services before switching modes. Startup logs are under `.run/`.

A startup check that stops its owned services afterward:

```sh
python -m speedmap.cli.launch demo --smoke-test
```

## Option B: start manually in two terminals

### Terminal 1: Python setup and API

Create/activate the environment as in [the data guide](fetching_data.md#1-create-the-python-environment), then install application/development dependencies and the package:

```sh
python -m pip install -r requirements-dev.txt
python -m pip install -e . --no-deps
```

Linux/macOS, starting with a data-free demo:

```sh
SPEEDMAP_MODE=demo python -m uvicorn speedmap.api.main:app --host 127.0.0.1 --port 8000
```

Windows PowerShell:

```powershell
$env:SPEEDMAP_MODE = 'demo'
python -m uvicorn speedmap.api.main:app --host 127.0.0.1 --port 8000
```

To switch modes, stop the API, set `SPEEDMAP_MODE` to a value described in [Choose the operating mode](#choose-the-operating-mode), and start the API again. For example, use `SPEEDMAP_MODE=data python -m uvicorn speedmap.api.main:app --host 127.0.0.1 --port 8000` on Linux/macOS, or set `$env:SPEEDMAP_MODE = 'data'` in PowerShell before running the Uvicorn command. If `SPEEDMAP_MODE` is unset, manual startup defaults to `actual`. A PowerShell assignment persists in that shell; use `Remove-Item Env:SPEEDMAP_MODE` to restore the default.

Set `SPEEDMAP_ROOT` before starting the launcher or API to use a different data/artifact root with the same `data/` and `artifacts/` layout, including `data/reference/`. Unset it to use the repository root. The provided Compose configuration does not forward this variable.

For model mode, `SPEEDMAP_MODEL_NAME` defaults to `regional`. Leave `SPEEDMAP_MODEL_RUN` unset to load `LATEST`, or set it to a run directory name from `artifacts/models/regional/`. Use the scikit-learn version recorded in that run's metadata. Restart after changing data, artifacts, or environment variables.

### Terminal 2: frontend

```sh
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open **http://127.0.0.1:5173**. Vite proxies `/api` to port 8000. Keep both terminals running, then stop each with **Ctrl+C** when finished. `npm ci` is needed for first setup and after lockfile changes.

## Check readiness and try a region

Open these URLs:

- http://127.0.0.1:8000/api/health — `ready`, resolved `mode`, `model_loaded`, tower provenance and available data metadata.
- http://127.0.0.1:8000/docs — interactive API documentation.
- http://127.0.0.1:8000/api/predict?lat=21.0285&lon=105.8542 — Hoàn Kiếm response.

In the UI, choose **Hoàn Kiếm**, enter coordinates or click inside Hanoi. Read the regional download speed and quality, radius circle and sampling support. Model mode adds grid samples when fewer than five measured tiles lie inside the radius; those sparse estimates have different support from measured regions. Data mode does not invent measurements for empty regions. Towers and the Hanoi boundary can be toggled under **Layers**; the About button opens the project's About page.

Map tiles require internet access. Optional fonts have local fallbacks. If tiles fail, the local prediction service and coordinate/neighbourhood controls can still work. Browser location is requested only when selected, and points outside Hanoi are rejected.

## Docker option

With Docker Compose available, from the root:

```sh
docker compose up --build
```

The default is `actual` mode. Compose mounts local processed/interim data and model artifacts read-only, so prepare them first. Open **http://127.0.0.1:8080**. Nginx forwards `/api` to the backend; port 8000 is also published locally.

For a data-free Docker demo on Linux/macOS:

```sh
SPEEDMAP_MODE=demo docker compose up --build
```

In PowerShell, set `$env:SPEEDMAP_MODE = 'demo'` before the Compose command. Stop any service already using port 8000 first. Shut down with `docker compose down`.

## Troubleshooting and checks

- **503/unavailable:** read `.run/` or backend logs. Data mode needs valid tile/tower files; model mode needs matching data fingerprints and a compatible saved bundle. It never silently substitutes demo results.
- **Port in use:** stop the existing launcher/server, or reuse the same mode. Keep 8000/5173 unless also changing the frontend proxy.
- **No module named speedmap:** install the editable package with the same Python interpreter used for Uvicorn.
- **No recorded region:** use a better-observed location or a trained model; a distant nearest tile is not presented as a measured regional average.

From `frontend/`, run `npm run lint` and `npm run build`. Browser tests require an activated Python environment, then `npx playwright install chromium` and `npm run test:e2e`. They cover desktop/mobile and can reuse local demo servers; stop a model/data server first. See [the API contract](api_contract.md) for response fields and [the application guide](application.md) for development details.
