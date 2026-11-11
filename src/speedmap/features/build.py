"""Build the training tables: cleaned Ookla + point features.   Owner: Person 1

Outputs (columns in docs/data_contract.md):
- data/processed/hanoi_tiles.csv  one row per tile, speeds pooled over the latest quarters (recommended)
- data/processed/hanoi_train.csv  one row per tile and quarter
Both use the same PointFeaturizer, which the backend also uses for clicked points.
"""
import warnings

import numpy as np
import pandas as pd

from speedmap import config
from speedmap.features.point_features import PointFeaturizer
from speedmap.features.spatial import spatial_block_id

TILE_INFO = ["quadkey", "latitude", "longitude", "first_quarter", "last_quarter", "quarters",
             "download_mbps", "upload_mbps", "latency_ms", "tests", "devices", "reliability"]
LABELS = [config.WEIGHT_COLUMN, config.GROUP_COLUMN, "quality_level"]
TRAIN_INFO = ["quarter", "quarter_index", "quadkey", "latitude", "longitude",
              "download_mbps", "upload_mbps", "latency_ms", "tests", "devices"]


def reliability(tests: int) -> str:
    return next(name for upper, name in config.RELIABILITY_LEVELS if tests < upper)


def _weighted_log_mean(values: pd.Series, weights: pd.Series) -> float:
    # Trung bình log có trọng số theo số test: ít bị kéo bởi vài ô cực nhanh/chậm
    return float(np.expm1(np.average(np.log1p(values.clip(lower=0)), weights=weights)))


def pool_tiles(ookla_clean: pd.DataFrame, n_quarters: int = config.POOL_QUARTERS) -> pd.DataFrame:
    """One row per tile: speeds pooled over the latest n_quarters, weighted by the number of tests."""
    latest = sorted(ookla_clean["quarter_index"].unique())[-n_quarters:]
    recent = ookla_clean[ookla_clean["quarter_index"].isin(latest)]
    rows = []
    for quadkey, t in recent.groupby("quadkey"):
        rows.append({
            "quadkey": str(quadkey),
            "latitude": t["latitude"].iloc[0],
            "longitude": t["longitude"].iloc[0],
            "first_quarter": t.loc[t["quarter_index"].idxmin(), "quarter"],
            "last_quarter": t.loc[t["quarter_index"].idxmax(), "quarter"],
            "quarters": t["quarter"].nunique(),
            "download_mbps": round(_weighted_log_mean(t["download_mbps"], t["tests"]), 2),
            "upload_mbps": round(_weighted_log_mean(t["upload_mbps"], t["tests"]), 2),
            "latency_ms": round(float(np.average(t["latency_ms"], weights=t["tests"])), 1),
            "tests": int(t["tests"].sum()),
            "devices": int(t["devices"].sum()),
        })
    tiles = pd.DataFrame(rows)
    tiles["reliability"] = tiles["tests"].map(reliability)
    return tiles


def _add_labels(df: pd.DataFrame) -> pd.DataFrame:
    df[config.WEIGHT_COLUMN] = np.sqrt(df["tests"]).round(3)
    df[config.GROUP_COLUMN] = spatial_block_id(df["latitude"], df["longitude"])
    df["quality_level"] = df[config.TARGET_COLUMN].map(config.quality_level)
    return df


def _features_for_tiles(points: pd.DataFrame, featurizer: PointFeaturizer) -> pd.DataFrame:
    feats = featurizer.features(points["latitude"].to_numpy(), points["longitude"].to_numpy())
    feats = feats.drop(columns=["latitude", "longitude"])
    feats.insert(0, "quadkey", points["quadkey"].astype(str).to_numpy())
    return feats


def build_tile_table(ookla_clean: pd.DataFrame, towers: pd.DataFrame, cells: pd.DataFrame,
                     *, include_physics: bool = True) -> pd.DataFrame:
    """hanoi_tiles.csv: pooled tiles + all features. The pooled tiles are also the activity source."""
    tiles = pool_tiles(ookla_clean)
    featurizer = PointFeaturizer(towers, cells, tiles, include_physics=include_physics)
    df = tiles.merge(_features_for_tiles(tiles, featurizer), on="quadkey", how="left")
    df = _add_labels(df)
    cols = TILE_INFO + [c for c in config.FEATURE_COLUMNS if c not in ("latitude", "longitude")] + LABELS
    validate_training_table(df, include_physics=include_physics)
    return df[cols].reset_index(drop=True)


def build_training_table(ookla_clean: pd.DataFrame, towers: pd.DataFrame, cells: pd.DataFrame,
                         tiles: pd.DataFrame, *, include_physics: bool = True) -> pd.DataFrame:
    """hanoi_train.csv: one row per tile and quarter, same features (activity from the pooled tiles)."""
    featurizer = PointFeaturizer(towers, cells, tiles, include_physics=include_physics)
    points = ookla_clean.drop_duplicates("quadkey")[["quadkey", "latitude", "longitude"]].copy()
    points["quadkey"] = points["quadkey"].astype(str)
    df = ookla_clean.assign(quadkey=ookla_clean["quadkey"].astype(str)).merge(
        _features_for_tiles(points, featurizer), on="quadkey", how="left")
    df = _add_labels(df)
    cols = TRAIN_INFO + [c for c in config.FEATURE_COLUMNS if c not in ("latitude", "longitude")] + LABELS
    validate_training_table(df, include_physics=include_physics)
    return df[cols].sort_values(["quarter_index", "quadkey"]).reset_index(drop=True)


def validate_training_table(df: pd.DataFrame, *, include_physics: bool = True) -> None:
    """Raise an error if required columns are missing or contain invalid values."""
    required = config.FEATURE_COLUMNS + [config.TARGET_COLUMN, config.WEIGHT_COLUMN, config.GROUP_COLUMN, "tests"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    must_be_complete = [c for c in required if c not in config.OPTIONAL_FEATURES]
    bad = [c for c in must_be_complete if df[c].isna().any()]
    if bad:
        raise ValueError(f"Missing values in: {bad}")
    if (df[config.TARGET_COLUMN] <= 0).any():
        raise ValueError("download_mbps must be positive")
    if include_physics and df["theory_mbps"].isna().any():
        warnings.warn("theory_mbps is empty: rebuild the table after the physics module is finished")
