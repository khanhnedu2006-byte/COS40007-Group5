"""Evaluate and save the physics-only 3GPP link-budget ablation.

Run from the repository root with the project virtual environment::

    .venv/bin/python -m speedmap.cli.train_physics_only

The script uses the same five spatial folds and evaluation-row filter as the
baseline models. It writes ``artifacts/reports/cv_physics_only.csv`` and saves
the model under ``artifacts/models/physics_only``.
"""

import hashlib

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from speedmap import config
from speedmap.artifacts import save_model
from speedmap.evaluation.metrics import mae, rmse
from speedmap.models.hybrid import PhysicsOnly


def evaluate_physics_only(
    data: pd.DataFrame,
    n_folds: int = config.CV_FOLDS,
) -> pd.DataFrame:
    """Evaluate physics-only across complete spatial blocks."""
    results: list[dict[str, int | float | str]] = []
    splitter = GroupKFold(n_splits=n_folds)
    for fold, (train_idx, test_idx) in enumerate(
        splitter.split(data, groups=data[config.GROUP_COLUMN]), start=1
    ):
        train = data.iloc[train_idx]
        test = data.iloc[test_idx]
        test = test[test["tests"] >= config.MIN_TESTS_FOR_EVAL]
        if test.empty:
            raise ValueError(f"Fold {fold} has no test rows with enough speed tests")

        model = PhysicsOnly().fit(
            train,
            train[config.TARGET_COLUMN].to_numpy(),
        )
        actual = test[config.TARGET_COLUMN].to_numpy()
        predicted = model.predict(test)
        level_matches = [
            config.quality_level(actual_value) == config.quality_level(predicted_value)
            for actual_value, predicted_value in zip(actual, predicted)
        ]
        results.append(
            {
                "fold": fold,
                "model": "physics_only",
                "train_rows": len(train),
                "test_rows_scored": len(test),
                "mae": mae(actual, predicted),
                "rmse": rmse(actual, predicted),
                "level_accuracy": float(np.mean(level_matches)),
            }
        )
    return pd.DataFrame(results)


def main() -> None:
    """Evaluate physics-only, then save the report and model."""
    data = pd.read_csv(config.TRAIN_FILE, dtype={"quadkey": str})
    from speedmap.data.boundary import require_study_area

    require_study_area(data)
    results = evaluate_physics_only(data)

    config.ARTIFACTS_REPORTS.mkdir(parents=True, exist_ok=True)
    report_path = config.ARTIFACTS_REPORTS / "cv_physics_only.csv"
    results.to_csv(report_path, index=False)
    metrics = {
        name: float(results[name].mean()) for name in ("mae", "rmse", "level_accuracy")
    }

    final_model = PhysicsOnly().fit(
        data,
        data[config.TARGET_COLUMN].to_numpy(),
    )
    input_digest = hashlib.sha256(config.TRAIN_FILE.read_bytes()).hexdigest()
    run_dir = save_model(
        final_model,
        "physics_only",
        metrics=metrics,
        params=final_model.get_params(),
        feature_columns=final_model.columns,
        notes=(
            f"Spatial {config.CV_FOLDS}-fold CV; test rows require >= "
            f"{config.MIN_TESTS_FOR_EVAL} tests; 3GPP link-budget ablation; "
            f"training file SHA-256: {input_digest}"
        ),
    )

    print(results.to_string(index=False))
    print(f"\nMean fold metrics: {metrics}")
    print(f"Report: {report_path}")
    print(f"Model: {run_dir}")


if __name__ == "__main__":
    main()
