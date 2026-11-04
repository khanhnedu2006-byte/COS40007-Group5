# Hanoi Signal

### Good places. Better signal.

An interactive map for exploring mobile internet performance across **Hanoi, Vietnam**. Choose a neighbourhood or click a location to see a speed estimate, its range, and the nearest cell locations.

Built for **COS40007 — Artificial Intelligence Engineering** at Swinburne University of Technology.

> **Current status: local demo.** The web application runs while the team develops the prediction model. In demo mode, **speeds, ranges and tower locations are simulated**. No dataset or trained model is needed to start the website.

**Windows quick launch:** double-click **[demo.bat](demo.bat)** for simulated predictions or **[start.bat](start.bat)** for the actual saved model. Install Python and Node.js first; the launchers handle project dependencies and open the browser.

[Double-click launch](#double-click-on-windows) · [Manual setup](#before-you-start) · [Docker](#run-with-docker) · [Model integration](#connect-the-trained-model) · [Development checks](#development-checks) · [Documentation](#documentation)

## What you can explore

- **Hanoi only:** map navigation stays around the city, with predictions restricted to its administrative boundary.
- **Pick a place:** click the map, enter coordinates, or try Hoàn Kiếm, West Lake, Cầu Giấy and Hà Đông.
- **Understand the result:** download speed, upload speed, latency, a speed range and a quality level.
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
| **[start.bat](start.bat)** | The website using the team's actual saved model and tower data. |

Double-click the launcher you want. On the first run, it creates `.venv/` and installs dependencies automatically; this needs internet access. Later runs skip installation unless requirements or the frontend lockfile change. The browser opens at **http://127.0.0.1:5173** when both services are ready.

Keep the launcher window open while using the website. Press **Enter** there to stop the services it started. If the same mode is already running, the launcher reopens it. Close the existing launcher or manually started servers before switching modes. Startup logs are saved under `.run/`.

`start.bat` does not train a model or substitute demo data: it reports missing model files or startup errors. See [model integration](#connect-the-trained-model) before using it. It respects `SPEEDMAP_MODEL_NAME` and `SPEEDMAP_MODEL_RUN` when set; otherwise it uses `hybrid` and its `LATEST` pointer. Additional model dependencies can be listed in `requirements-model.txt`.

### Before you start

Install **Python 3.11** (the version used in CI) and **Node.js 22.13 or later in the Node 22 release line**, including npm. Clone or download this repository, then open a terminal in its root folder — the folder containing `README.md`, `backend/` and `frontend/`.

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

Open **[http://127.0.0.1:8080](http://127.0.0.1:8080)**. Nginx serves the frontend and forwards API requests to FastAPI. The Compose stack uses demo mode.

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

The planned model combines **3GPP physics and XGBoost**, with KNN and Random Forest baselines and an **80% conformal prediction range**. Demo ranges are illustrative and have no measured confidence coverage.

## Connect the trained model

Double-click **`start.bat`** to launch in `model` mode. The model team must first provide the saved bundle, its metadata, the processed tower table and the completed shared physics code. The launcher installs the dependencies in `requirements-model.txt`; add any additional estimator dependencies there. Manual backend startup defaults to `SPEEDMAP_MODE=demo` unless configured otherwise.

Follow the **[model handoff guide](docs/application.md#switch-to-the-teams-trained-model)** and **[API contract](docs/api_contract.md)** for the expected files, bundle interface and environment settings.

Model mode never silently falls back to demo data. An incomplete or incompatible model setup leaves predictions unavailable and records the cause in the backend logs. Pin the agreed model run with `SPEEDMAP_MODEL_RUN`; otherwise the existing registry's `LATEST` pointer is used.

## Development checks

**Backend · Windows PowerShell, from the project root:**

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m ruff check backend src/speedmap/inference scripts/launch.py tests/test_api.py tests/test_predictor.py tests/test_launcher.py
.\.venv\Scripts\python.exe -m pytest tests/test_api.py tests/test_predictor.py tests/test_launcher.py tests/test_boundary.py tests/test_features.py tests/test_artifacts.py -q
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
| Model mode returns `503` | Check the backend logs and follow the model handoff guide. Confirm that the bundle, tower data and estimator dependencies are available. |
| Browser tests cannot start Python | Activate the backend virtual environment in the test terminal, or start the backend separately before running the tests. |

## Documentation

- [Application setup, model handoff and environment settings](docs/application.md)
- [API endpoints and saved-model bundle contract](docs/api_contract.md)
- [Training data contract](docs/data_contract.md)
- [Project background, scope and decisions](PROJECT_CONTEXT.md)

## Data and attribution

The planned prediction pipeline uses **[Ookla Open Data](https://github.com/teamookla/ookla-open-data)** (CC BY-NC-SA 4.0) and **[OpenCelliD](https://opencellid.org/)** (CC BY-SA 4.0). The Hanoi boundary comes from **[geoBoundaries](https://www.geoboundaries.org/)** (CC BY 4.0). The default basemap is © **[Stadia Maps](https://stadiamaps.com/attribution/)**, **[OpenMapTiles](https://openmaptiles.org/)** and **[OpenStreetMap contributors](https://www.openstreetmap.org/copyright)**; the detailed style uses OpenStreetMap tiles. Local Stadia development needs no API key; public hosting needs domain authentication as described in the [application guide](docs/application.md).

These credits describe the project data sources. The current demo's speeds and tower locations are simulated.
