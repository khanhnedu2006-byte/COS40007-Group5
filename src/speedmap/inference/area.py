"""Area estimate: typical speed within config.AREA_RADIUS_M (500 m) of a clicked point.   Owner: Person 1/3

Scores for the current training run are saved under artifacts/reports/regional.

How: the points of the area are the Ookla tile centres inside the circle, weighted by their number of tests
(where people actually use the network). If the circle has fewer than AREA_MIN_TILES tiles, grid points
every AREA_GRID_STEP_M are added with weight 1. The model predicts every point; the area value is the
weighted mean in log scale (same pooling as the training labels).
"""
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

from speedmap import config
from speedmap.features.spatial import EARTH_RADIUS_M, KM_PER_DEG_LAT


def weighted_log_mean(values_mbps, weights) -> float:
    values = np.asarray(values_mbps, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if values.ndim != 1 or weights.shape != values.shape or not len(values):
        raise ValueError("Speeds and weights must be non-empty, aligned vectors")
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Speeds must be finite and non-negative")
    if not np.isfinite(weights).all() or (weights <= 0).any():
        raise ValueError("Weights must be finite and positive")
    return float(np.expm1(np.average(np.log1p(values), weights=weights)))


class AreaSampler:
    def __init__(self, tiles: pd.DataFrame):
        if tiles.empty or not np.isfinite(tiles[["latitude", "longitude", "tests"]].to_numpy(dtype=float)).all():
            raise ValueError("Area sampler requires finite, non-empty tiles")
        if (tiles["tests"] <= 0).any():
            raise ValueError("Area sampler requires positive test counts")
        self.tiles = tiles.reset_index(drop=True)
        self.tree = BallTree(np.radians(self.tiles[["latitude", "longitude"]].to_numpy()), metric="haversine")

    @staticmethod
    def _grid(lat: float, lon: float, radius_m: float) -> pd.DataFrame:
        step_lat = config.AREA_GRID_STEP_M / (KM_PER_DEG_LAT * 1000)
        step_lon = config.AREA_GRID_STEP_M / (111_320 * np.cos(np.radians(lat)))
        n = int(radius_m // config.AREA_GRID_STEP_M)
        dy, dx = np.meshgrid(np.arange(-n, n + 1), np.arange(-n, n + 1), indexing="ij")
        keep = np.hypot(dy, dx) * config.AREA_GRID_STEP_M <= radius_m
        return pd.DataFrame({"latitude": lat + dy[keep] * step_lat, "longitude": lon + dx[keep] * step_lon,
                             "weight": 1.0, "source": "grid"})

    def points(self, lat: float, lon: float, radius_m: float = config.AREA_RADIUS_M) -> pd.DataFrame:
        idx = self.tree.query_radius(np.radians([[lat, lon]]), r=radius_m / EARTH_RADIUS_M)[0]
        pts = self.tiles.iloc[idx][["latitude", "longitude"]].assign(
            weight=self.tiles.iloc[idx]["tests"].to_numpy(dtype=float), source="ookla_tile")
        if len(pts) < config.AREA_MIN_TILES:
            pts = pd.concat([pts, self._grid(lat, lon, radius_m)], ignore_index=True)
        return pts.reset_index(drop=True)


def area_estimate(predict_mbps, featurizer, sampler: AreaSampler, lat: float, lon: float,
                  columns=None, radius_m: float = config.AREA_RADIUS_M) -> dict:
    """predict_mbps: function(features DataFrame) -> download Mbps for each row (e.g. bundle["model"].predict)."""
    pts = sampler.points(lat, lon, radius_m)
    feats = featurizer.features(pts["latitude"].to_numpy(), pts["longitude"].to_numpy())
    if columns is not None:
        feats = feats[columns]
    preds = np.asarray(predict_mbps(feats), dtype=float)
    value = round(weighted_log_mean(preds, pts["weight"]), 1)
    return {
        "area_radius_m": radius_m,
        "area_download_mbps": value,
        "area_quality_level": config.quality_level(value),
        "area_points": len(pts),
        "area_ookla_tiles": int((pts["source"] == "ookla_tile").sum()),
        "area_grid_points": int((pts["source"] == "grid").sum()),
    }
