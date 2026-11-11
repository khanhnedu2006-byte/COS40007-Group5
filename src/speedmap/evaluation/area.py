"""Area-level evaluation for the 500 m click radius.   Owner: Person 2 (helper written by Person 1)

Each tile centre acts as a click. Truth = test-weighted log mean of the MEASURED speeds of the tiles in the
circle; prediction = same pooling of the out-of-fold PREDICTED speeds. Only circles with >= min_tests tests count.
Use out-of-fold predictions from spatial block CV, otherwise the score is too optimistic.
"""
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

from speedmap import config
from speedmap.features.spatial import EARTH_RADIUS_M


def area_level_scores(tiles: pd.DataFrame, pred_mbps, radius_m: float = config.AREA_RADIUS_M,
                      min_tests: int = 30) -> dict:
    lat_lon = np.radians(tiles[["latitude", "longitude"]].to_numpy())
    idx = BallTree(lat_lon, metric="haversine").query_radius(lat_lon, r=radius_m / EARTH_RADIUS_M)
    true_log = np.log1p(tiles["download_mbps"].to_numpy(dtype=float))
    pred_log = np.log1p(np.clip(np.asarray(pred_mbps, dtype=float), 0, None))
    tests = tiles["tests"].to_numpy(dtype=float)
    total = np.array([tests[ix].sum() for ix in idx])
    keep = total >= min_tests
    truth = np.expm1([np.average(true_log[ix], weights=tests[ix]) for ix, k in zip(idx, keep) if k])
    pred = np.expm1([np.average(pred_log[ix], weights=tests[ix]) for ix, k in zip(idx, keep) if k])
    upper = [u for u, _ in config.QUALITY_LEVELS[:-1]]
    lt, lp = np.digitize(truth, upper), np.digitize(pred, upper)
    return {
        "radius_m": radius_m,
        "n_areas": int(keep.sum()),
        "share_of_clicks_evaluated": float(keep.mean()),
        "level_accuracy": float(np.mean(lt == lp)),
        "within_one_level": float(np.mean(np.abs(lt - lp) <= 1)),
        "majority_baseline": float(np.bincount(lt).max() / len(lt)),
        "mae_mbps": float(np.mean(np.abs(truth - pred))),
    }
