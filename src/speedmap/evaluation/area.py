"""Area-level evaluation for the 500 m click radius.   Owner: Person 2 (helper written by Person 1)

Each tile centre acts as a click. Truth = test-weighted log mean of the MEASURED speeds of the tiles in the
circle; prediction = same pooling of the out-of-fold PREDICTED speeds. Only circles with >= min_tests tests count.
Use out-of-fold predictions from spatial block CV, otherwise the score is too optimistic.
"""
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, mean_absolute_error
from sklearn.neighbors import BallTree

from speedmap import config
from speedmap.features.spatial import EARTH_RADIUS_M


def area_level_scores(tiles: pd.DataFrame, pred_mbps, radius_m: float = config.AREA_RADIUS_M,
                      min_tests: int = 30) -> dict:
    predictions = np.asarray(pred_mbps, dtype=float)
    if predictions.ndim != 1 or len(predictions) != len(tiles):
        raise ValueError("One aligned prediction per tile is required")
    if not np.isfinite(predictions).all() or (predictions < 0).any():
        raise ValueError("Predictions must be finite and non-negative")
    required = tiles[["latitude", "longitude", "download_mbps", "tests"]].to_numpy(dtype=float)
    if not len(tiles) or not np.isfinite(required).all():
        raise ValueError("Area scoring requires non-empty, finite tile data")
    if (tiles["tests"] <= 0).any() or (tiles["download_mbps"] < 0).any():
        raise ValueError("Test counts must be positive and speeds non-negative")
    if radius_m <= 0 or min_tests <= 0:
        raise ValueError("radius_m and min_tests must be positive")
    lat_lon = np.radians(tiles[["latitude", "longitude"]].to_numpy())
    idx = BallTree(lat_lon, metric="haversine").query_radius(lat_lon, r=radius_m / EARTH_RADIUS_M)
    true_log = np.log1p(tiles["download_mbps"].to_numpy(dtype=float))
    pred_log = np.log1p(predictions)
    tests = tiles["tests"].to_numpy(dtype=float)
    total = np.array([tests[ix].sum() for ix in idx])
    keep = total >= min_tests
    if not keep.any():
        return {"radius_m": radius_m, "n_areas": 0, "share_of_clicks_evaluated": 0.0,
                "level_accuracy": None, "within_one_level": None,
                "majority_baseline": None, "mae_mbps": None}
    truth = np.expm1([np.average(true_log[ix], weights=tests[ix]) for ix, k in zip(idx, keep) if k])
    pred = np.expm1([np.average(pred_log[ix], weights=tests[ix]) for ix, k in zip(idx, keep) if k])
    upper = [u for u, _ in config.QUALITY_LEVELS[:-1]]
    lt, lp = np.digitize(truth, upper), np.digitize(pred, upper)
    return {
        "radius_m": radius_m,
        "n_areas": int(keep.sum()),
        "share_of_clicks_evaluated": float(keep.mean()),
        "level_accuracy": float(accuracy_score(lt, lp)),
        "within_one_level": float(np.mean(np.abs(lt - lp) <= 1)),
        "majority_baseline": float(np.bincount(lt).max() / len(lt)),
        "mae_mbps": float(mean_absolute_error(truth, pred)),
    }
