"""Spatial block cross-validation.   Owner: Person 2

GroupKFold with groups = block_id keeps each block in one fold. Adjacent blocks
can still occur on opposite sides of a split. Predict all held-out tiles;
tile-level metrics alone use tests >= config.MIN_TESTS_FOR_EVAL.
"""
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from speedmap import config
from speedmap.evaluation.area import area_level_scores
from speedmap.evaluation.metrics import all_metrics
from speedmap.models.baselines import KNNBaseline, RandomForestBaseline

BASELINES = {"knn": KNNBaseline, "random_forest": RandomForestBaseline}


def spatial_folds(df: pd.DataFrame, n_folds: int = config.CV_FOLDS):
    """Yield (train_idx, test_idx) arrays using sklearn GroupKFold on config.GROUP_COLUMN."""
    return GroupKFold(n_splits=n_folds).split(df, groups=df[config.GROUP_COLUMN])


def evaluate_baselines(df: pd.DataFrame, n_folds: int = config.CV_FOLDS,
                       model_factories=None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return fold metrics, row-aligned OOF predictions, and tile/area summaries.

    Factory injection allows tests to verify held-out membership directly.
    No evaluation prediction is produced by the final all-data model.
    """
    factories = BASELINES if model_factories is None else model_factories
    if df["quadkey"].duplicated().any():
        raise ValueError("Regional training requires one pooled row per quadkey")
    oof = df[["quadkey", "latitude", "longitude", config.GROUP_COLUMN,
              "tests", config.TARGET_COLUMN]].reset_index(drop=True).copy()
    oof.insert(0, "row_position", np.arange(len(df)))
    oof["fold"] = 0
    for name in factories:
        oof[f"{name}_prediction_mbps"] = np.nan
    results = []
    for fold, (train_idx, test_idx) in enumerate(spatial_folds(df, n_folds), start=1):
        train, test = df.iloc[train_idx], df.iloc[test_idx]
        oof.loc[test_idx, "fold"] = fold
        for name, factory in factories.items():
            model = factory()
            weight_column = "tests" if name == "knn" else config.WEIGHT_COLUMN
            model.fit(train, train[config.TARGET_COLUMN].to_numpy(), train[weight_column].to_numpy())
            predictions = np.asarray(model.predict(test), dtype=float)
            if predictions.shape != (len(test),) or not np.isfinite(predictions).all() or (predictions < 0).any():
                raise ValueError(f"{name} returned invalid held-out predictions")
            oof.loc[test_idx, f"{name}_prediction_mbps"] = predictions
            score = test["tests"].to_numpy() >= config.MIN_TESTS_FOR_EVAL
            metrics = all_metrics(test.loc[score, config.TARGET_COLUMN], predictions[score]) if score.any() else {}
            results.append({"fold": fold, "model": name, "train_rows": len(train),
                            "test_rows": len(test), "test_rows_scored": int(score.sum()), **metrics})
    summaries = []
    eligible = df["tests"].to_numpy() >= config.MIN_TESTS_FOR_EVAL
    for name in factories:
        predictions = oof[f"{name}_prediction_mbps"].to_numpy()
        if (oof["fold"] == 0).any() or not np.isfinite(predictions).all():
            raise ValueError("Every tile must receive exactly one held-out prediction")
        area = area_level_scores(df, predictions)
        if area["n_areas"] == 0:
            raise ValueError("No regions have the 30 tests required for model selection")
        tile_metrics = all_metrics(df.loc[eligible, config.TARGET_COLUMN], predictions[eligible]) if eligible.any() else {}
        summaries.append({"model": name, **{f"tile_{k}": v for k, v in tile_metrics.items()},
                          **{f"area_{k}": v for k, v in area.items()}})
    summary = pd.DataFrame(summaries)
    summary["tie_priority"] = (summary["model"] != "knn").astype(int)
    summary = summary.sort_values(["area_mae_mbps", "area_level_accuracy", "tie_priority"],
                                  ascending=[True, False, True]).drop(columns="tie_priority").reset_index(drop=True)
    return pd.DataFrame(results), oof, summary


def split_calibration(train_idx: np.ndarray, groups: np.ndarray, share: float = config.CALIBRATION_SHARE, seed: int = 0):
    """Move a share of the training BLOCKS into a calibration set for the conformal range."""
    # TODO
    raise NotImplementedError


def cross_validate(df: pd.DataFrame, model_names: list, n_folds: int = config.CV_FOLDS) -> pd.DataFrame:
    """Compatibility entrypoint for pooled-tile baseline fold metrics."""
    return evaluate_baselines(df, n_folds, {name: BASELINES[name] for name in model_names})[0]


def summarise(results: pd.DataFrame) -> pd.DataFrame:
    """Mean of each metric per model, sorted by MAE."""
    return results.groupby("model")[["mae", "rmse", "level_accuracy"]].mean().sort_values("mae")
