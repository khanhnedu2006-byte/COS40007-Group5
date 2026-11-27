"""Reproducible pooled-tile baseline comparison and regional model selection."""

import hashlib
import json

import numpy as np
import pandas as pd
import sklearn

from speedmap import config
from speedmap.artifacts import save_model
from speedmap.evaluation.cv import BASELINES, REGIONAL_MODELS, evaluate_baselines
from speedmap.features.build import validate_training_table
from speedmap.data.boundary import require_study_area


def train_baselines():
    """Save the selected baseline plus CV evidence."""
    return _train(BASELINES, include_physics=False)


def train_regional():
    """Compare all regional candidates and save the selected model."""
    return _train(REGIONAL_MODELS, include_physics=True)


def _train(factories, include_physics):
    tiles = pd.read_csv(config.TILES_FILE, dtype={"quadkey": str})
    validate_training_table(tiles, include_physics=include_physics)
    require_study_area(tiles)
    if include_physics and (
        not np.isfinite(tiles["theory_mbps"].to_numpy(dtype=float)).all()
        or (tiles["theory_mbps"] < 0).any()
    ):
        raise ValueError(
            "Rebuild features with --step features --include-physics before regional model training"
        )
    folds, oof, summary = (
        evaluate_baselines(tiles, model_factories=factories)
        if include_physics
        else evaluate_baselines(tiles)
    )
    winner = summary.iloc[0]["model"]
    models = {}
    for name, factory in factories.items():
        weights = tiles["tests" if name == "knn" else config.WEIGHT_COLUMN].to_numpy()
        models[name] = factory().fit(
            tiles, tiles[config.TARGET_COLUMN].to_numpy(), weights
        )
    final_model = models[winner]

    inputs = [
        config.OOKLA_RAW_FILE,
        config.OPENCELLID_RAW_FILE,
        config.OSM_TOWERS_RAW_FILE,
        config.TILES_FILE,
        config.TOWERS_FILE,
        config.CELLS_FILE,
        config.HANOI_BOUNDARY_FILE,
        config.CONTEXT_GRID_FILE,
    ]
    fingerprints = {
        str(path.relative_to(config.ROOT)): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in inputs
        if path.is_file()
    }
    provenance = {
        "input_sha256": fingerprints,
        "sklearn_version": sklearn.__version__,
        "training_rows": len(tiles),
        "pool_quarters": config.POOL_QUARTERS,
        "first_quarter": str(tiles["first_quarter"].min()),
        "last_quarter": str(tiles["last_quarter"].max()),
        "cv_folds": config.CV_FOLDS,
        "spatial_block_km": config.SPATIAL_BLOCK_KM,
        "area_radius_m": config.AREA_RADIUS_M,
        "area_min_tests": 30,
        "model_settings": {
            name: factory().get_params() for name, factory in factories.items()
        },
        "selection": "lowest area MAE, then highest area level accuracy, then model name",
        "evaluation": "spatial out-of-fold; model-selection estimate, not independent holdout",
    }
    metrics = summary.iloc[0].drop("model").to_dict()
    bundle = {
        "kind": "regional_model" if include_physics else "regional_baseline",
        "model": final_model,
        "models": models,
        "model_name": winner,
        "area_radius_m": config.AREA_RADIUS_M,
        "include_physics": winner in {"hybrid", "physics_only"},
    }
    run_dir = save_model(
        bundle,
        "regional",
        metrics=metrics,
        params=final_model.get_params(),
        feature_columns=final_model.columns,
        provenance=provenance,
        notes=f"Selected {winner} using pooled-tile spatial out-of-fold regional MAE.",
    )
    report_root = config.ARTIFACTS_REPORTS / "regional"
    report_dir = report_root / run_dir.name
    report_dir.mkdir(parents=True)
    folds.to_csv(report_dir / "fold_metrics.csv", index=False)
    oof.to_csv(report_dir / "out_of_fold.csv", index=False)
    summary.to_csv(report_dir / "summary.csv", index=False)
    (report_dir / "manifest.json").write_text(
        json.dumps(
            {"run_id": run_dir.name, "selected_model": winner, **provenance}, indent=2
        ),
        encoding="utf-8",
    )
    (report_root / "LATEST").write_text(run_dir.name, encoding="utf-8")
    print(summary.to_string(index=False))
    print(f"Selected model: {winner}\nModel: {run_dir}\nReports: {report_dir}")
    return run_dir, report_dir
