# Regional baseline training and evaluation

## Prerequisites

Use the Python environment from [Fetch and prepare data](fetching_data.md). With it active, install `python -m pip install -r requirements-dev.txt` and `python -m pip install -e . --no-deps`. These baseline commands do not require TensorFlow or the Intel scikit-learn extension. Raw data is not included in a clone; fetch it or obtain matching processed tables from the data owner first.

The required prepared files are `hanoi_tiles.csv`, `hanoi_towers.csv` and `hanoi_cells.csv`, plus the checked-in boundary/context grid. Run commands from the repository root. Activate `.venv` on Linux/macOS or `.venv\Scripts\Activate.ps1` in PowerShell, or use that environment's Python executable directly.

## Reproduce a run

Install the application/development requirements and the editable package. From the root, with that Python environment active:

```sh
python scripts/run_pipeline.py --step towers
python scripts/run_pipeline.py --step features
python scripts/train_baselines.py
```

The first two steps rebuild generated data from local raw inputs: Ookla mobile tiles, OpenCelliD cells, optional OSM masts, the boundary and context grid. They do not download inputs. `python scripts/run_pipeline.py --step baselines` is an equivalent training entrypoint. Avoid `--step all` while the separate hybrid pipeline is unfinished.

Feature generation skips physics by default for the regional baselines and prints an informational message. The `theory_mbps` column remains empty to preserve the shared table schema; it is excluded by both models. Baseline training and serving do not call the unfinished physics functions. To explicitly attempt the physics feature for separate hybrid work, run `python scripts/run_pipeline.py --step features --include-physics`; that path still warns until physics is implemented.

The training table is `data/processed/hanoi_tiles.csv`, containing one observation per tile pooled over the latest four available quarters. For each tile, download is `expm1(sum(tests * log1p(speed)) / sum(tests))`. Preserve quadkeys as strings. All tiles, including those with few tests, participate in training and out-of-fold regional pooling.

## Models and preprocessing

- KNN uses ten distinct geographic neighbours, uniform neighbour weights, and haversine distance. Repeated coordinates are combined using test-count-weighted targets within the training partition.
- Random Forest uses 300 trees, minimum five samples per leaf, seed 42, and all shared features except `theory_mbps`. Training weights are `sqrt(tests)`.
- Missing optional context values use training-fold medians. Entirely missing columns are retained and filled with zero. The fitted imputer is saved with Random Forest and reused during inference. Required non-context features must be finite.
- Neither model needs physics. Neither uses target speeds from neighbouring tiles as input features. Device-count/activity features use the full pooled sampling table; this evaluation assumes those unlabeled counts and static context are available at prediction time. It does not simulate completely unobserved infrastructure or future quarters.

## Out-of-fold evaluation

Use five identical `GroupKFold` splits for both models, grouping by 2 km `block_id`. Every tile is held out once. Predict **all** held-out rows and write their values back to their original row positions. Never score predictions from the model fitted on all data.

Tile metrics use held-out rows with at least three tests. Regional metrics call `area_level_scores(tiles, out_of_fold_predictions)` on the complete aligned vectors. Each tile centre acts as a click: collect measured tile centres within 500 m, then compute the test-weighted log mean of actual speeds and, separately, predicted speeds. Only circles with at least 30 total tests are scored. Each qualifying circle has equal influence on the reported metric; test counts weight pooling within it.

MAE and RMSE use scikit-learn's `mean_absolute_error` and `root_mean_squared_error`. Quality accuracy uses `accuracy_score` after assigning Poor (<15 Mbps), Fair (15–<100), Good (100–<200), or Excellent (>=200). Within-one-level accuracy and support coverage are project-specific calculations. The majority baseline predicts the most common true regional category.

Select the lowest regional MAE; ties prefer higher regional quality accuracy, then KNN. Fit that model on all pooled tiles using the same settings. There is no hyperparameter search in this comparison.

## Artifacts and provenance

Models are saved to `artifacts/models/regional/<run>/`, with `model.joblib`, `metadata.json`, and a parent `LATEST` pointer. Models and processed data are local generated artifacts excluded from Git.

Evidence is saved to `artifacts/reports/regional/<run>/`:

- `fold_metrics.csv`: held-out tile metrics and row counts for each fold/model.
- `out_of_fold.csv`: row position, quadkey, coordinates, block, tests, measured target, fold ID, and each model's prediction. Read with `dtype={"quadkey": str}`.
- `summary.csv`: pooled held-out tile metrics and regional metrics, ordered by selection criteria. A mean of fold metrics may differ from the pooled metric because fold sizes differ.
- `manifest.json`: selected model, settings for both candidates, training period, scikit-learn version and SHA-256 fingerprints of available input files. The same provenance is embedded in model metadata. The shared registry also records canonical data fingerprints and verifies them at model startup to reject stale inputs. The report directory has its own `LATEST` pointer.

Use a compatible runtime, including the recorded scikit-learn version, to load joblib artifacts. Supply the matching processed tiles, towers, cells and context grid when serving them. Pin the run with `SPEEDMAP_MODEL_RUN` and restart the API after changing it.

## Current comparison: 500 m

Run `20261111-152722` reran the five identical spatial folds on the same 5,212 pooled tiles and refitted the selected winner. The scoring radius is **500 m**; the 2 km CV blocks, model settings, data, and 30-test minimum are unchanged.

- **Random Forest selected:** regional MAE **33.539987 Mbps**, exact-quality accuracy **69.5438%**, within-one-level accuracy **99.2602%**.
- **KNN:** regional MAE **35.955053 Mbps**, exact-quality accuracy **68.1874%**, within-one-level accuracy **98.5203%**.
- **Support:** **811 / 5,212 regions (15.5602%)** meet the evaluation threshold. Majority-quality baseline: **68.6806%** on those regions. The small margin over the majority baseline limits what exact-category accuracy alone demonstrates.

Tile-centre spacing is at least approximately **569 m** in the current data. A 500 m circle centred on a measured tile therefore contains just that one measured tile. Arbitrary UI centres can include several tiles; at Hoàn Kiếm the current model samples three measured centres and nine grid points. The unchanged sparse-area rule adds a 300 m grid whenever fewer than five measured centres lie within the circle. This produces nine grid points for a 500 m circle, including its centre. Evaluation has targets only at measured centres and does not validate those extra grid samples.

Changing this radius changes regional pooling and model selection, not the per-tile training inputs. Refitting is not inherently necessary just to pool at another radius, but the old 1.5 km metrics do not apply. Here the 500 m comparison selected a different winner, so the final Random Forest was fitted and saved in a new bundle with `area_radius_m=500`. Old runs keep their saved radius when explicitly pinned. Restart the API and clear any old `SPEEDMAP_MODEL_RUN` pin to load the new `LATEST` run.

The 500 m output is more local, but does not establish finer ground-truth resolution or change KNN's ten-neighbour search. Coverage and eligible regions differ from the 1.5 km evaluation, so the accuracy percentages are not directly comparable.

## Historical comparison: 1.5 km, 11 November 2026

Run `20261111-133102` used **5,212 tiles**, pooled over **2025 Q4–2026 Q3**, in **831 spatial blocks**. Of the tile-centred circles, **4,175 (80.10%)** met the 30-test requirement.

- **KNN selected:** regional MAE **20.797954 Mbps**, regional quality accuracy **73.8443%**. Tile MAE **52.279081 Mbps**, RMSE **71.740475 Mbps**, quality accuracy **53.4152%**.
- **Random Forest:** regional MAE **24.033741 Mbps**, regional quality accuracy **63.2575%**. Tile MAE **49.452430 Mbps**, RMSE **67.486507 Mbps**, quality accuracy **53.4452%**.
- Regional majority baseline: **56.5269%**. Both models were within one quality level on **100%** of evaluated circles; this coarse metric should be read alongside MAE and exact-category accuracy.

## Interpretation and limits

These are spatial out-of-fold **model-selection estimates**, not independent final holdout results. Spatial blocks prevent sharing the same block between train and test, but adjacent blocks can cross folds. Overlapping circles share observations, and a circle can combine out-of-fold predictions made by different fitted models. Results therefore do not measure generalization to an entirely unseen region with a spatial exclusion buffer.

Evaluation uses measured tile centres only. Sparse production circles add grid samples, which have no measured targets and are not covered by the regional accuracy claim. Sampling weights describe where tests were observed, not uniform population or land-area coverage. Excluded low-support circles may perform differently. The four-quarter pool estimates typical recent performance rather than future-quarter forecasting, live network load, or a particular operator's service. No calibrated regional uncertainty interval is supplied.

## Run the trained model and repeat evaluation

The training command evaluates first, then saves the all-data fit; rerun `python scripts/train_baselines.py` to repeat the comparison and create a new model/report run. There is no separate command that substitutes training-set predictions for the saved OOF report. Inspect `summary.csv` for regional metrics and `out_of_fold.csv` for individual held-out predictions and fold IDs.

Start `python scripts/launch.py model` or follow [Run the Web UI](running_web_ui.md). `actual` mode also selects the registered regional model when present; `data` mode displays recorded regional measurements without evaluating a trained model. Data mode's observed averages are not a CV accuracy report.

Regression checks, with the Python environment active:

```sh
python -m pytest tests/test_regional_training.py tests/test_knn.py tests/test_random_forest.py tests/test_area.py tests/test_features.py tests/test_predictor.py -q
```

The separate `model.py` TensorFlow/Group Task 2 exercise consumes tile-quarter rows and writes `metrics.txt` and `model_results.png`; it does not create the regional app bundle or the spatial OOF comparison described here. Its `python model.py --check-data` validates inputs without TensorFlow. `python model.py --data-file data/ci/hanoi_train.csv --check-data` also checks the committed CI snapshot manifest. Refresh that snapshot with `python scripts/sync_ci_data.py` when intentionally updating the canonical data. The legacy individual baseline scripts likewise do not select or save the app's `regional` bundle.

If you need to reproduce the separate TensorFlow exercise, use a compatible Python 3.11 environment, install its TensorFlow dependency, then run:

```sh
python -m pip install tensorflow
python model.py --check-data
python model.py
```

That exercise's split and metrics are separate from the spatial regional comparison. Its outputs do not replace `area_level_scores` on spatial out-of-fold predictions, and its trained network is not loaded by the regional Web UI.

## Intel scikit-learn acceleration

`patch_sklearn()` is already present before scikit-learn imports in the legacy individual KNN/Random Forest scripts. It does not accelerate the current canonical baseline configuration: haversine/BallTree KNN is unsupported, and the weighted Random Forest with bootstrapping falls back to standard scikit-learn. This was checked with the installed scikit-learn 1.9.1 / scikit-learn-intelex 2026.2.0; verbose dispatch confirmed fallback for both forest fit and predict. Adding patch calls to metrics, splitters, or BallTree helpers would not speed this run.

The geographic metric and test-count training weights are preserved. No new acceleration dependency or globally patched estimator is introduced by the 500 m change. If settings change to a supported configuration later, patch once before estimator imports and record both library versions; accelerated serialized estimators also require compatible Intel dependencies when loaded. See the [official supported algorithms](https://github.com/uxlfoundation/scikit-learn-intelex/blob/main/doc/sources/algorithms.rst) and [patching guide](https://github.com/uxlfoundation/scikit-learn-intelex/blob/main/doc/sources/patching.rst).
