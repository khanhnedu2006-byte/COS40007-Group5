# Hanoi Signal

### Good places. Better signal.

An interactive map for exploring mobile internet performance across **Hanoi, Vietnam**. Choose a neighbourhood or click a location to see typical download speed within a **1.5 km radius**, its quality level, and the nearest cell locations.

Built for **COS40007 — Artificial Intelligence Engineering** at Swinburne University of Technology.

> **Current status: regional baseline and recorded-data modes available.** The default `actual` mode selects a registered regional model, otherwise recorded-data estimates. Demo speeds are simulated; tower locations use local data when available.

**Windows quick launch:** double-click **[demo.bat](demo.bat)** for simulated predictions or **[start.bat](start.bat)** for actual mode (registered model or recorded data). Install Python and Node.js first; the launchers handle project dependencies and open the browser.

[Double-click launch](#double-click-on-windows) · [Manual setup](#before-you-start) · [Docker](#run-with-docker) · [Model integration](#connect-the-trained-model) · [Development checks](#development-checks) · [Documentation](#documentation)

## Step-by-step guides

1. [Fetch and prepare data](docs/fetching_data.md) — downloads, local inputs, optional context layers and processed tables.
2. [Run and evaluate models](docs/training.md) — baseline comparison, spatial OOF metrics, artifacts and results.
3. [Run the Web UI](docs/running_web_ui.md) — setup, operating modes, launchers, manual startup and Docker.

## What you can explore

- **Hanoi only:** map navigation stays around the city, with predictions restricted to its administrative boundary.
- **Pick a place:** click the map, enter coordinates, or try Hoàn Kiếm, West Lake, Cầu Giấy and Hà Đông.
- **Understand the region:** typical download speed, a quality level and a 1.5 km circle. Sampling support identifies sparse regions that need extra grid points.
- **Focus on performance:** a quiet basemap and a selected location coloured by download quality. Tower markers and nearest-tower connections are optional under Layers.
- **Use desktop or mobile:** a responsive interface with loading, error and reconnection states.

The project treats **4G and 5G together**. It estimates typical area performance rather than running a live speed test or predicting a particular operator's network.

## Start the website

On Windows, use the double-click launchers below. Manual startup with two terminals is also available.

### Double-click on Windows

Install the Python and Node.js prerequisites listed below, then open this folder in File Explorer:

If Windows hides file extensions, the launchers appear as **demo** and **start**.

| Launcher | What it starts |
| --- | --- |
| **[demo.bat](demo.bat)** | The website with simulated predictions. No dataset or model required. |
| **[start.bat](start.bat)** | The website using actual mode: a registered model, otherwise recorded data. |

Double-click the launcher you want. It uses this computer's Python installation and prints the selected version. On the first run, it creates `.venv/` and installs dependencies automatically; this needs internet access. A copied, broken or incompatible `.venv/` is preserved as `.venv.backup-<timestamp>/` and replaced with a fresh environment. Later runs skip installation unless the Python runtime, project location, requirements or frontend dependencies change. The browser opens at **http://127.0.0.1:5173** when both services are ready.

Keep the launcher window open while using the website. Press **Enter** there to stop the services it started. If the same mode is already running, the launcher reopens it. Close the existing launcher or manually started servers before switching modes. Startup logs are saved under `.run/`.

`start.bat` does not train a model: it selects a registered regional model when available, otherwise recorded-data estimates. An invalid registered model fails readiness; demo mode must be selected explicitly. See [model integration](#connect-the-trained-model) before using it. It respects `SPEEDMAP_MODEL_NAME` and `SPEEDMAP_MODEL_RUN` when set; otherwise it uses `regional` and its `LATEST` pointer. Additional model dependencies can be listed in `requirements-model.txt`.

### Before you start

Install **64-bit Python 3.11 or newer, including Python 3.14.7**, with pip, and **Node.js 22.13 or later in the Node 22 release line**, including npm. Make Python available through `python` on PATH or the Windows `py` launcher. Clone or download this repository, then open a terminal in its root folder — the folder containing `README.md`, `backend/` and `frontend/`.

When transferring the project to another computer, copy the source files rather than `.venv/`, `.venv.backup-*/`, `frontend/node_modules/` or `.run/`. These are generated locally and are already excluded from Git. Double-click `demo.bat` on the new computer to create its own environment.

Check your tools:

```sh
python --version
node --version
npm --version
```

On macOS/Linux, use `python3` if `python` is unavailable.

### 1. Set up and start the backend manually

**Windows · PowerShell** — run these commands from the project root:

```powershell
# One-time setup
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install -e . --no-deps

# Start the API in demo mode
$env:SPEEDMAP_MODE = 'demo'
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

These commands use the virtual environment directly; activating it is optional. Leave this terminal running.

<details>
<summary><strong>macOS / Linux instructions</strong></summary>

Run from the project root:

```sh
# One-time setup
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip install -e . --no-deps

# Start the API in demo mode
SPEEDMAP_MODE=demo .venv/bin/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Leave this terminal running.

</details>

### 2. Start the frontend in a second terminal

Open a **new terminal in the project root**, then run:

```sh
cd frontend
npm ci
npm run dev
```

Leave this terminal running too. `npm ci` installs the frontend dependencies from the lockfile; it is needed on first setup and when dependencies change.

### 3. Open the website

| Service | Local address |
| --- | --- |
| **Web application** | **[http://127.0.0.1:5173](http://127.0.0.1:5173)** |
| Interactive API documentation | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) |
| API health and operating mode | [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health) |

Choose **Hoàn Kiếm** to try your first prediction. The header should show **Demo mode**.

**Next time:** double-click `demo.bat` or `start.bat` again. For manual startup, skip the one-time installation commands, start the backend and run `npm run dev` from `frontend/`. Stop launcher-managed services with **Enter** in the launcher window; stop manually started servers with **Ctrl+C** in their terminals.

Map tiles need an internet connection. The default **Signal focus** style is intentionally quiet; switch to **Detailed streets** under Layers when you need more map detail. The demo prediction service runs locally; optional web fonts load separately and fall back to system fonts if unavailable.

## Run with Docker

A Compose configuration is included to run the backend and frontend together. Install Docker Desktop with Docker Compose, start Docker, and run from the project root:

```sh
docker compose up --build
```

Open **[http://127.0.0.1:8080](http://127.0.0.1:8080)**. Nginx serves the frontend and forwards API requests to FastAPI. The Compose stack defaults to actual mode and mounts the local data/model directories. Prepare data first, or set `SPEEDMAP_MODE=demo` for a data-free demonstration.

Stop an existing backend on port `8000` before starting Compose; both setups use that port. To stop and remove the Compose containers, run this in another terminal:

```sh
docker compose down
```

## How it fits together

```text
React + Leaflet map
        |
        |  /api/predict, /api/towers, /api/boundary
        v
FastAPI backend
        |
        +-- Demo mode: deterministic simulated data
        |
        +-- Model mode: shared features -> saved model bundle
```

The app serves the selected **KNN or Random Forest baseline**, pooling point predictions into a test-weighted regional log mean. The physics/hybrid pipeline remains separate and unfinished. Regional results have no calibrated uncertainty interval.

## Connect the trained model

Train from the available raw Ookla, OpenCelliD and optional OSM inputs, using the checked-in context grid. In an environment installed with `requirements-dev.txt` and the editable package, run from the repository root:

```sh
python scripts/run_pipeline.py --step towers
python scripts/run_pipeline.py --step features
python scripts/train_baselines.py
```

This creates the processed cell/tower tables, pools the latest four quarters into one observation per tile, compares both baselines on five spatial folds, and saves the regional winner. Physics is not required. Raw inputs and generated models/data are excluded from Git; retain them when handing off a trained run. Use the same scikit-learn version recorded in the model metadata when loading a saved model.

The feature step skips physics by default and leaves the unused `theory_mbps` column empty. `--include-physics` explicitly attempts that feature for the separate hybrid workflow, where unfinished-physics warnings still apply.

The model is saved under `artifacts/models/regional/<run>/`. Evidence is saved under `artifacts/reports/regional/<run>/`: `summary.csv`, `fold_metrics.csv`, `out_of_fold.csv` and `manifest.json`. Each parent directory has a `LATEST` pointer. Read the [training and evaluation guide](docs/training.md) for metric definitions and limitations. The older individual baseline scripts evaluate tile-quarter data and do not create the app's regional bundle.

The 11 November 2026 run selected **KNN**: regional MAE **20.80 Mbps**, quality-level accuracy **73.84%**, compared with Random Forest's **24.03 Mbps** and **63.26%**. Scores cover **4,175 of 5,212** tile-centred regions (80.10%), with at least 30 tests per region. The majority-quality baseline is **56.53%**. These are out-of-fold model-selection results, not an independent holdout estimate.

Double-click **`start.bat`**, or start the backend manually on macOS/Linux:

```sh
SPEEDMAP_MODE=model .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In PowerShell, set `$env:SPEEDMAP_MODE = 'model'` before starting Uvicorn. Start the frontend as above. `SPEEDMAP_MODEL_NAME` defaults to `regional`; set `SPEEDMAP_MODEL_RUN` to pin a saved run or leave it unset to load `LATEST`. Model mode reports missing/incompatible artifacts as unavailable and never substitutes demo data.

See the [model handoff guide](docs/application.md#switch-to-the-teams-trained-model) and [regional API contract](docs/api_contract.md).

## Development checks

**Backend · Windows PowerShell, from the project root:**

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m ruff check backend src/speedmap/inference scripts/launch.py tests/test_api.py tests/test_predictor.py tests/test_launcher.py
.\.venv\Scripts\python.exe -m pytest tests/test_api.py tests/test_predictor.py tests/test_launcher.py tests/test_boundary.py tests/test_features.py tests/test_context.py tests/test_artifacts.py tests/test_regional_training.py tests/test_area.py tests/test_knn.py tests/test_random_forest.py -q
```

On macOS/Linux, replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`.

**Frontend · from `frontend/`:**

```sh
npm run lint
npm run build
```

The production build is written to `frontend/dist/`.

**Desktop and mobile browser tests · from `frontend/`:**

```sh
# First time: install the test browser
npx playwright install chromium

# Use the backend virtual environment, then run the tests
npm run test:e2e
```

Browser tests can reuse running local servers in demo mode. If you have stopped them, activate the backend virtual environment in the test terminal first so Playwright can start Python itself: `..\.venv\Scripts\Activate.ps1` on Windows or `source ../.venv/bin/activate` on macOS/Linux.

Application checks work without a trained model. The full `pytest` suite also includes physics tests for model components still under development; the focused command above matches application CI.

## Repository guide

```text
backend/                  FastAPI endpoints, response schemas and demo predictor
frontend/                 React interface, Leaflet map and browser tests
src/speedmap/             Shared Python package
  data/                   Dataset loading, tower processing and Hanoi boundary
  features/               Shared spatial and tower features
  physics/                3GPP propagation and link budget
  models/                 Baselines, hybrid model and conformal ranges
  evaluation/             Spatial cross-validation, metrics and figures
  inference/              Saved-model adapter used by the backend
notebooks/                Data exploration, training and evaluation
scripts/                  Data downloads and pipeline entry points
data/                     Raw, interim, processed and reference data
artifacts/                Model runs and report figures
tests/                    Python tests
docs/                     Application guide and shared contracts
.github/workflows/        Application checks and training workflow
compose.yaml              Local Docker stack
```

Reusable logic belongs in `src/speedmap/`; notebooks call those functions so training and inference can share the same code. The older `ml/` directory contains earlier prototypes. Some data and model components remain marked `TODO` or `NotImplementedError`.

### Team responsibilities

| Area | Responsibilities |
| --- | --- |
| Data and testing | Data ingestion and cleaning, tower features, dataset contract and end-to-end testing. |
| Models and MLOps | Physics, baselines, hybrid model, uncertainty ranges, evaluation, model registry and retraining. |
| Application and DevOps | Frontend, backend, prediction integration, API contract, CI, Docker and deployment preparation. |

### Continuous integration

| Workflow | Purpose |
| --- | --- |
| [Application CI](.github/workflows/application.yml) | Python lint and interface tests, notebook-output checks, frontend lint/build, browser tests and a Docker Compose smoke test. |
| [Train ML Model](.github/workflows/train.yml) | The separate Group Task 2 TensorFlow workflow. Runs `model.py` on `data/ci/hanoi_train.csv` and uploads the results. |

Both workflows target pushes and pull requests to `main` and support manual runs. Public deployment is not configured yet.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| The page opens, but the service is offline | Keep the backend terminal running. Check the health URL, then click **Reconnect**. |
| `No module named speedmap` | Run the editable installation command from the project root using the same virtual environment as the backend. |
| Port `5173` or `8000` is already in use | Stop the other local instance. Keep the documented ports unless you also update the proxy configuration. |
| The map background does not load | Check internet access or switch to **Detailed streets** under Layers. Neighbourhood shortcuts and coordinate entry still work. |
| A location is rejected | Predictions are available only inside Hanoi's administrative boundary, including when using browser location. |
| The health response says `model_loaded: false` | This is expected in demo mode. Check `ready` and `mode` as well. |
| A copied project reports a missing Python installation | Update the launcher files and run `demo.bat` again. It validates the local Python runtime and backs up an incompatible `.venv/` before creating a new one. |
| Python 3.14 setup fails | Use 64-bit Python with pip and the latest launcher. Setup upgrades packaging tools before installing the application dependencies. Read the printed Python version and last error lines; model/training dependencies may have separate requirements. |
| Model mode returns `503` | Check the backend logs and follow the model handoff guide. Confirm that the bundle, tower data and estimator dependencies are available. |
| Browser tests cannot start Python | Activate the backend virtual environment in the test terminal, or start the backend separately before running the tests. |

## Documentation

- [Fetch and prepare data](docs/fetching_data.md)
- [Run the Web UI](docs/running_web_ui.md)
- [Application setup, model handoff and environment settings](docs/application.md)
- [API endpoints and saved-model bundle contract](docs/api_contract.md)
- [Training data contract](docs/data_contract.md)
- [Regional training, evaluation and results](docs/training.md)
- [Project background, scope and decisions](PROJECT_CONTEXT.md)

## Data and attribution

The prediction pipeline uses **[Ookla Open Data](https://github.com/teamookla/ookla-open-data)** (CC BY-NC-SA 4.0) and **[OpenCelliD](https://opencellid.org/)** (CC BY-SA 4.0). The Hanoi boundary comes from **[geoBoundaries](https://www.geoboundaries.org/)** (CC BY 4.0). The default basemap is © **[Stadia Maps](https://stadiamaps.com/attribution/)**, **[OpenMapTiles](https://openmaptiles.org/)** and **[OpenStreetMap contributors](https://www.openstreetmap.org/copyright)**; the detailed style uses OpenStreetMap tiles. Local Stadia development needs no API key; public hosting needs domain authentication as described in the [application guide](docs/application.md).

These credits describe the project data sources. Demo speeds are simulated; tower locations use the local dataset when available, otherwise simulated locations.
