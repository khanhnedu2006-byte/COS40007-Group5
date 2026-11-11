# Run the Web UI

Hanoi Signal has a FastAPI backend on port **8000** and a React/Vite frontend on **5173**. Start from the repository root. Use 64-bit Python 3.11+ and Node.js 22.13+ in the Node 22 line, or Node.js 24+. The launcher checks these prerequisites.

## Choose the operating mode

- **`actual` (default):** selects the registered regional model if its `LATEST` pointer or a pinned run exists; otherwise selects recorded-data mode. A broken registered model reports an error instead of silently switching modes.
- **`data`:** uses current recorded Ookla tiles and tower locations without a trained model. Needs `data/interim/hanoi_towers.csv` and `data/processed/hanoi_tiles.csv`. The main reading is the test-weighted regional recorded speed, where observed tiles exist within 500 m. Regions without observations are identified as unavailable.
- **`model`:** strictly loads the saved regional baseline. Requires a model from [the training guide](training.md), matching processed towers/cells/tiles, and reference data. Missing, stale or incompatible artifacts leave the API unavailable.
- **`demo`:** generates simulated regional speeds without a trained model. Uses the local tower table when available; otherwise uses simulated towers. An invalid existing tower file is reported rather than silently replaced. Simulated speeds are labeled separately from tower provenance.

For real-data preparation, follow [Fetch and prepare data](fetching_data.md). Model output is typical download performance within **500 m** of a chosen centre. It is not a live speed test or an operator-specific prediction.

## Option A: launch both services together

On Windows, double-click:

- `start.bat` for `actual` mode.
- `demo.bat` for simulated speeds.

The launchers create/check the local environment, install dependencies when needed, start both services, verify readiness and open the browser. First setup needs internet access. An incompatible copied environment is preserved as a backup and recreated.

Alternatively, from a terminal on any supported platform:

```sh
python scripts/launch.py actual
```

Replace `actual` with `data`, `model`, or `demo` to select a mode explicitly. Use the Python interpreter available on your system (`python3` on some Linux/macOS installations, or `py -3` on Windows).

Keep the launcher console open. Press **Enter** there to stop services it started. It can reuse ready services of the same resolved mode; stop existing services before switching modes. Startup logs are under `.run/`.

A startup check that stops its owned services afterward:

```sh
python scripts/launch.py demo --smoke-test
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
SPEEDMAP_MODE=demo python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Windows PowerShell:

```powershell
$env:SPEEDMAP_MODE = 'demo'
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Change the mode to `actual`, `data`, or `model` after preparing the corresponding inputs. If `SPEEDMAP_MODE` is unset, manual startup defaults to `actual`.

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
