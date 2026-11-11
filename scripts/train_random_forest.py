"""Evaluate and save the non-physics Random Forest baseline.

Run from the repository root with the project virtual environment::

    .venv/bin/python scripts/train_random_forest.py

The script uses the same five spatial folds and evaluation-row filter as the
KNN baseline. It writes ``artifacts/reports/cv_random_forest.csv`` and saves a
model fitted on all rows under ``artifacts/models/random_forest``.
"""
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Apply Intel Extension optimizations before importing any scikit-learn module.
# Unsupported estimators or parameter combinations automatically use the normal
# scikit-learn implementation, so the training result remains compatible.
from sklearnex import patch_sklearn

patch_sklearn()

from sklearn.model_selection import GroupKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from speedmap import config  # noqa: E402
from speedmap.artifacts import save_model  # noqa: E402
from speedmap.evaluation.metrics import mae, rmse  # noqa: E402
from speedmap.models.baselines import RandomForestBaseline  # noqa: E402


def evaluate_random_forest(
    data: pd.DataFrame,
    n_estimators: int = 300,
    min_samples_leaf: int = 5,
    n_folds: int = config.CV_FOLDS,
) -> pd.DataFrame:
    """Evaluate Random Forest while holding out complete spatial blocks.

    @param data: Training table containing model features, download target,
        sample weights, test counts, and spatial block IDs.
    @type data: pandas.DataFrame
    @param n_estimators: Number of decision trees in each fold's forest.
    @type n_estimators: int
    @param min_samples_leaf: Minimum number of rows allowed in a tree leaf.
    @type min_samples_leaf: int
    @param n_folds: Number of spatial GroupKFold splits.
    @type n_folds: int
    @return: One metrics row per fold.
    @rtype: pandas.DataFrame
    """
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

        model = RandomForestBaseline(
            n_estimators=n_estimators,
            min_samples_leaf=min_samples_leaf,
        ).fit(
            train,
            train[config.TARGET_COLUMN].to_numpy(),
            train[config.WEIGHT_COLUMN].to_numpy(),
        )
        actual = test[config.TARGET_COLUMN].to_numpy()
        predicted = model.predict(test)
        level_matches = [
            config.quality_level(actual_value)
            == config.quality_level(predicted_value)
            for actual_value, predicted_value in zip(actual, predicted)
        ]
        results.append(
            {
                "fold": fold,
                "model": "random_forest",
                "train_rows": len(train),
                "test_rows_scored": len(test),
                "mae": mae(actual, predicted),
                "rmse": rmse(actual, predicted),
                "level_accuracy": float(np.mean(level_matches)),
            }
        )
    return pd.DataFrame(results)


def main() -> None:
    """Evaluate Random Forest, then save the report and final fitted model."""
    data = pd.read_csv(config.TRAIN_FILE, dtype={"quadkey": str})
    results = evaluate_random_forest(data)

    config.ARTIFACTS_REPORTS.mkdir(parents=True, exist_ok=True)
    report_path = config.ARTIFACTS_REPORTS / "cv_random_forest.csv"
    results.to_csv(report_path, index=False)
    metrics = {
        name: float(results[name].mean())
        for name in ("mae", "rmse", "level_accuracy")
    }

    final_model = RandomForestBaseline().fit(
        data,
        data[config.TARGET_COLUMN].to_numpy(),
        data[config.WEIGHT_COLUMN].to_numpy(),
    )
    input_digest = hashlib.sha256(config.TRAIN_FILE.read_bytes()).hexdigest()
    run_dir = save_model(
        final_model,
        "random_forest",
        metrics=metrics,
        params=final_model.get_params(),
        feature_columns=final_model.columns,
        notes=(
            f"Spatial {config.CV_FOLDS}-fold CV; test rows require >= "
            f"{config.MIN_TESTS_FOR_EVAL} tests; fitted with {config.WEIGHT_COLUMN}; "
            f"theory_mbps excluded; training file SHA-256: {input_digest}"
        ),
    )

    print(results.to_string(index=False))
    print(f"\nMean fold metrics: {metrics}")
    print(f"Report: {report_path}")
    print(f"Model: {run_dir}")


if __name__ == "__main__":
    main()
