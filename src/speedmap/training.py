"""Reproducible pooled-tile baseline comparison and regional model selection."""
import hashlib
import json

import pandas as pd
import sklearn

from speedmap import config
from speedmap.artifacts import save_model
from speedmap.evaluation.cv import BASELINES, evaluate_baselines
from speedmap.features.build import validate_training_table


def train_baselines():
    """Save the selected model plus CV evidence; return model and report paths."""
    tiles = pd.read_csv(config.TILES_FILE, dtype={"quadkey": str})
    validate_training_table(tiles, include_physics=False)
    folds, oof, summary = evaluate_baselines(tiles)
    winner = summary.iloc[0]["model"]
    final_model = BASELINES[winner]()
    weights = tiles["tests" if winner == "knn" else config.WEIGHT_COLUMN].to_numpy()
    final_model.fit(tiles, tiles[config.TARGET_COLUMN].to_numpy(), weights)

    inputs = [config.OOKLA_RAW_FILE, config.OPENCELLID_RAW_FILE, config.OSM_TOWERS_RAW_FILE,
              config.TILES_FILE, config.TOWERS_FILE, config.CELLS_FILE,
              config.HANOI_BOUNDARY_FILE, config.CONTEXT_GRID_FILE]
    fingerprints = {str(path.relative_to(config.ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in inputs if path.is_file()}
    provenance = {
        "input_sha256": fingerprints, "sklearn_version": sklearn.__version__,
        "training_rows": len(tiles), "pool_quarters": config.POOL_QUARTERS,
        "first_quarter": str(tiles["first_quarter"].min()),
        "last_quarter": str(tiles["last_quarter"].max()),
        "cv_folds": config.CV_FOLDS, "spatial_block_km": config.SPATIAL_BLOCK_KM,
        "area_radius_m": config.AREA_RADIUS_M, "area_min_tests": 30,
        "model_settings": {name: factory().get_params() for name, factory in BASELINES.items()},
        "selection": "lowest area MAE, then highest area level accuracy, then KNN",
        "evaluation": "spatial out-of-fold; model-selection estimate, not independent holdout",
    }
    metrics = summary.iloc[0].drop("model").to_dict()
    bundle = {"kind": "regional_baseline", "model": final_model, "model_name": winner,
              "area_radius_m": config.AREA_RADIUS_M}
    run_dir = save_model(bundle, "regional", metrics=metrics, params=final_model.get_params(),
                         feature_columns=final_model.columns, provenance=provenance,
                         notes=f"Selected {winner} using pooled-tile spatial out-of-fold regional MAE.")
    report_root = config.ARTIFACTS_REPORTS / "regional"
    report_dir = report_root / run_dir.name
    report_dir.mkdir(parents=True)
    folds.to_csv(report_dir / "fold_metrics.csv", index=False)
    oof.to_csv(report_dir / "out_of_fold.csv", index=False)
    summary.to_csv(report_dir / "summary.csv", index=False)
    (report_dir / "manifest.json").write_text(json.dumps(
        {"run_id": run_dir.name, "selected_model": winner, **provenance}, indent=2), encoding="utf-8")
    (report_root / "LATEST").write_text(run_dir.name, encoding="utf-8")
    print(summary.to_string(index=False))
    print(f"Selected model: {winner}\nModel: {run_dir}\nReports: {report_dir}")
    return run_dir, report_dir
