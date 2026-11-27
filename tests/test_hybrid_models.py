"""Physics-guided models, spatial calibration and regional integration."""

import joblib
import numpy as np
import pandas as pd
import pytest

from speedmap import config
from speedmap.evaluation.cv import evaluate_baselines, split_calibration
from speedmap.evaluation.metrics import coverage
from speedmap.models.conformal import ConformalInterval
from speedmap.models.hybrid import HybridModel, PhysicsOnly, XGBoostOnly
from tests.test_regional_training import tile_rows


def test_hybrid_and_xgboost_fit_predict_and_serialize(tmp_path):
    rows = tile_rows().reset_index(drop=True)
    rows["theory_mbps"] = 150.0
    rows[config.CONTEXT_FEATURES] = np.nan
    for cls in (HybridModel, XGBoostOnly):
        model = cls(n_estimators=5, max_depth=2, n_jobs=1).fit(
            rows, rows.download_mbps, rows.sample_weight
        )
        predictions = model.predict(rows)
        assert predictions.shape == (len(rows),)
        assert np.isfinite(predictions).all() and (predictions >= 0).all()
        path = tmp_path / f"{cls.__name__}.joblib"
        joblib.dump(model, path)
        np.testing.assert_allclose(joblib.load(path).predict(rows), predictions)
        assert ("theory_mbps" in model.columns) == (cls is HybridModel)
    assert np.isfinite(
        HybridModel(n_estimators=2, n_jobs=1)
        .fit(rows, rows.download_mbps)
        .correction(rows)
    ).all()
    with pytest.raises(ValueError, match="theory_mbps"):
        HybridModel().fit(rows.assign(theory_mbps=np.nan), rows.download_mbps)
    np.testing.assert_array_equal(
        PhysicsOnly().fit(rows, rows.download_mbps).predict(rows), rows.theory_mbps
    )


def test_conformal_finite_sample_rank_and_validation():
    interval = ConformalInterval(0.8).calibrate(np.arange(1, 10), np.zeros(9))
    assert interval.q == 8
    low, high = interval.interval(np.array([2.0, 10.0]))
    np.testing.assert_equal(low, [0, 2])
    np.testing.assert_equal(high, [10, 18])
    assert coverage(np.array([0, 18]), low, high) == 1
    with pytest.raises(ValueError, match="enough"):
        ConformalInterval(0.8).calibrate([1], [0])
    with pytest.raises(ValueError, match="Calibrate"):
        ConformalInterval().interval([1])


def test_calibration_and_oof_are_block_separated():
    rows = tile_rows().reset_index(drop=True)
    rows["theory_mbps"] = 100.0
    fit, cal = split_calibration(
        np.arange(len(rows)), rows.block_id.to_numpy(), share=0.34
    )
    assert set(rows.iloc[fit].block_id).isdisjoint(rows.iloc[cal].block_id)
    folds, oof, summary = evaluate_baselines(
        rows,
        n_folds=3,
        model_factories={
            "hybrid": lambda: HybridModel(n_estimators=2, max_depth=2, n_jobs=1),
            "physics_only": PhysicsOnly,
            "xgboost_only": lambda: XGBoostOnly(n_estimators=2, max_depth=2, n_jobs=1),
        },
    )
    assert oof.filter(like="_prediction_mbps").notna().all().all()
    assert set(summary.model) == {"hybrid", "physics_only", "xgboost_only"}
    hybrid = folds[folds.model == "hybrid"]
    assert hybrid.coverage.between(0, 1).all()
    assert (hybrid.interval_width >= 0).all()


def test_regional_training_saves_a_reloadable_winner(tmp_path, monkeypatch):
    from speedmap import training
    from speedmap.artifacts import load_model

    rows = tile_rows().reset_index(drop=True)
    rows["theory_mbps"] = 100.0
    for name, path in {
        "ROOT": tmp_path,
        "ARTIFACTS_MODELS": tmp_path / "models",
        "ARTIFACTS_REPORTS": tmp_path / "reports",
        "TILES_FILE": tmp_path / "tiles.csv",
    }.items():
        monkeypatch.setattr(config, name, path)
    for name in [
        "OOKLA_RAW_FILE",
        "OPENCELLID_RAW_FILE",
        "OSM_TOWERS_RAW_FILE",
        "TOWERS_FILE",
        "CELLS_FILE",
        "HANOI_BOUNDARY_FILE",
        "CONTEXT_GRID_FILE",
    ]:
        monkeypatch.setattr(config, name, tmp_path / name)
    rows.to_csv(config.TILES_FILE, index=False)
    factories = {
        "hybrid": lambda: HybridModel(n_estimators=2, n_jobs=1),
        "physics_only": PhysicsOnly,
        "xgboost_only": lambda: XGBoostOnly(n_estimators=2, n_jobs=1),
    }
    monkeypatch.setattr(training, "REGIONAL_MODELS", factories)
    model_dir, report_dir = training.train_regional()
    bundle, meta = load_model("regional", model_dir.name)
    assert bundle["kind"] == "regional_model"
    assert bundle["model_name"] in factories
    assert meta["feature_columns"] == bundle["model"].columns
    assert len(pd.read_csv(report_dir / "out_of_fold.csv")) == len(rows)
    assert np.isfinite(bundle["model"].predict(rows)).all()


def test_standalone_cv_evaluators_return_expected_schema():
    from speedmap.cli.train_hybrid import evaluate_hybrid
    from speedmap.cli.train_physics_only import evaluate_physics_only
    from speedmap.cli.train_xgboost_only import evaluate_xgboost_only

    rows = tile_rows().reset_index(drop=True)
    rows["theory_mbps"] = 100.0
    expected_columns = [
        "fold",
        "model",
        "train_rows",
        "test_rows_scored",
        "mae",
        "rmse",
        "level_accuracy",
    ]
    fast_params = {"n_estimators": 2, "max_depth": 2, "n_jobs": 1}
    checks = [
        ("xgboost_only", evaluate_xgboost_only(rows, n_folds=3, **fast_params)),
        ("hybrid", evaluate_hybrid(rows, n_folds=3, **fast_params)),
        ("physics_only", evaluate_physics_only(rows, n_folds=3)),
    ]
    for name, frame in checks:
        assert list(frame.columns) == expected_columns
        assert len(frame) == 3
        assert (frame["model"] == name).all()
        assert np.isfinite(frame[["mae", "rmse"]]).all().all()
        assert (frame[["mae", "rmse"]] >= 0).all().all()
        assert frame["level_accuracy"].between(0, 1).all()
