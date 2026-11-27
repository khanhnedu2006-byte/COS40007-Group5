# Fetch and prepare Hanoi data

Use this guide before [training models](training.md) or running the Web UI in recorded-data mode. Run commands from the repository root after installing the package. Raw data and generated interim/processed tables are excluded from Git; cloning the source alone does not provide them. Set `SPEEDMAP_ROOT` before running Python to use a different root with the same `data/` and `artifacts/` layout, including the reference files. Explicit relative paths such as `--out` resolve from the current working directory.

## 1. Create the Python environment

Use 64-bit Python 3.11+ for the application and baselines. The separate TensorFlow exercise has its own dependency constraints; TensorFlow is not required for this workflow.

Linux/macOS:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt duckdb
python -m pip install -e . --no-deps
```

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt duckdb
python -m pip install -e . --no-deps
```

If activation is unavailable, replace `python` in the following commands with `.venv/bin/python` on Linux/macOS or `.\.venv\Scripts\python.exe` on Windows. Do not copy a virtual environment from another machine.

## 2. Fetch Ookla mobile observations

```sh
python -m speedmap.cli.fetch_ookla_hanoi
```

The script reads Ookla's public Parquet data through DuckDB and filters the Hanoi envelope. It writes `data/raw/ookla_hanoi_mobile.csv`. Exact 12-district study-area filtering happens during feature preparation.

The script's default is **2024 Q4 through 2026 Q3**, not a rolling latest-quarter query. To select quarters explicitly:

```sh
python -m speedmap.cli.fetch_ookla_hanoi --quarters 2025-4 2026-1 2026-2 2026-3 --kind mobile --out data/raw/ookla_hanoi_mobile.csv
```

The selected quarters replace the output CSV; use a separate `--out` path if preserving another download. Failed quarters are printed as `skipped`; inspect the log and retry before treating the download as complete. If every quarter fails, the script exits without a new dataset. DuckDB's `httpfs` extension and the remote data both require internet access.

## 3. Obtain OpenCelliD cells

This repository does not include an authenticated OpenCelliD downloader.

1. Open the [official OpenCelliD data downloads page](https://opencellid.org/downloads.php).
2. Use your account's API access token in the portal to access country exports.
3. Download the Vietnam/MCC **452** CSV export and save the gzip-compressed file as `data/raw/452.csv.gz`. Keep the supplied CSV column order; the loader handles the optional header and gzip compression.

Keep access tokens outside the repository. Country exports change over time, so new downloads can produce different counts and model results. OpenCelliD positions are estimated cell locations, rather than an official tower inventory. Retain source attribution when sharing derived outputs.

## 4. Fetch optional OSM masts

```sh
python -m speedmap.cli.fetch_osm_towers
```

Output: `data/raw/osm_comm_towers.csv`. The preparation step adds qualifying telecom masts that are sufficiently far from existing OpenCelliD locations. This input is optional; OpenCelliD remains required. The script tries several Overpass endpoints. Retry if all endpoints fail.

## 5. Prepare towers, cells, and feature tables

The repository already contains the 12-district study-area boundary and `data/reference/hanoi_context_grid.npz`; keep those reference files in place. With the raw observations and cells available:

```sh
python -m speedmap.cli.run_pipeline --step towers
python -m speedmap.cli.run_pipeline --step features
```

The tower step writes:

- `data/interim/hanoi_towers.csv`: merged OpenCelliD locations plus optional OSM masts.
- `data/interim/hanoi_cells.csv`: individual filtered cells for density/operator features.

The feature step writes:

- `data/interim/ookla_clean.csv`: cleaned observations inside Hanoi.
- `data/processed/hanoi_tiles.csv`: one observation per tile, pooled over the latest four quarters available in the raw file; input to regional baseline training and recorded-data mode.
- `data/processed/hanoi_train.csv`: one observation per tile-quarter; used by the separate TensorFlow exercise.
- `data/ci/hanoi_train.csv` and its manifest: refreshed automatically from the canonical tile-quarter table. These are tracked; review their diff when preparing a data update.

Physics is skipped by default. The unused `theory_mbps` column remains empty and does not prevent baseline training. For the five-model comparison, install `requirements-model.txt`, rebuild features with `--step features --include-physics`, then run `--step hybrid`. `--step all` also builds the physics feature and runs that comparison; it additionally requires context inputs for the context step.

The 18 November 12-district rebuild produced 1,882 towers, 2,779 cells, 852 pooled tiles, and 6,232 tile-quarter records. These are reference counts, not required values for a newer download. Preserve quadkeys as strings when loading CSVs.

## Optional: refresh context layers

Skip this section when using the checked-in context grid. Rebuilding context can download approximately 0.6–0.9 GB and requires additional raster tooling.

```sh
python -m pip install rasterio
python -m speedmap.cli.fetch_context_data
python -m speedmap.cli.fetch_places
python -m speedmap.cli.run_pipeline --step context
python -m speedmap.cli.run_pipeline --step features
```

`speedmap.cli.fetch_context_data` downloads population, land-cover, elevation, roads and OSM POIs to `data/raw/context/`, skipping files already present. `speedmap.cli.fetch_places` supplies Overture POIs as an alternative to Overpass POIs; the context builder prefers `overture_places.json` when present. The context step rebuilds `data/reference/hanoi_context_grid.npz` from available layers. Check downloader output for failures or missing layers before using the rebuilt grid.

## Verify and continue

```sh
python -m speedmap.cli.group_task_model --check-data
```

This validates the canonical tile-quarter table and prints its source, dimensions, period and fingerprint without importing TensorFlow. To refresh only the CI copy after a deliberate training-table update, run `python -m speedmap.cli.sync_ci_data`.

Changing processed inputs can invalidate saved models. Retrain against the new inputs and restart the API after updates; strict model mode reports a fingerprint mismatch instead of using stale inputs.

Continue with [Run and evaluate models](training.md) or [Run the Web UI](running_web_ui.md). See [the data contract](data_contract.md) for columns and units.
