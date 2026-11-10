"""Context features around any point from data/reference/hanoi_context_grid.npz.   Owner: Person 1

Square windows on a ~100 m grid (fast enough for every click). If the grid file or a layer is
missing, the feature is NaN (XGBoost handles missing values).
"""
import warnings

import numpy as np
import pandas as pd

from speedmap import config

# (tên feature, lớp, bán kính m, "sum" hoặc "mean")
CONTEXT_SPEC = [
    ("population_500m", "population", 500, "sum"),
    ("population_1km", "population", 1000, "sum"),
    ("builtup_500m", "builtup", 500, "mean"),
    ("builtup_1km", "builtup", 1000, "mean"),
    ("trees_1km", "trees", 1000, "mean"),
    ("cropland_1km", "cropland", 1000, "mean"),
    ("water_1km", "water", 1000, "mean"),
    ("elevation_m", "elevation_m", 0, "mean"),
    ("slope_deg", "slope_deg", 0, "mean"),
    ("roads_km_1km", "roads_km", 1000, "sum"),
    ("pois_1km", "pois", 1000, "sum"),
]


class ContextGrid:
    def __init__(self, layers: dict, lat_max: float, lon_min: float, res: float):
        self.lat_max, self.lon_min, self.res = lat_max, lon_min, res
        self.layers = layers
        self.shape = next(iter(layers.values())).shape if layers else (0, 0)
        lat0 = config.HANOI_CENTER[0]
        self.cell_y_m = res * 110_570
        self.cell_x_m = res * 111_320 * np.cos(np.radians(lat0))
        self._sat = {}

    @classmethod
    def load(cls, path=config.CONTEXT_GRID_FILE):
        if not path.exists():
            return None
        npz = np.load(path)
        lat_max, lon_min, res = npz["_meta"]
        return cls({k: npz[k] for k in npz.files if k != "_meta"}, float(lat_max), float(lon_min), float(res))

    def _tables(self, layer):
        # Bảng tổng tích luỹ (summed-area table): tổng trong một ô vuông bất kỳ chỉ cần 4 phép tra
        if layer not in self._sat:
            a = self.layers[layer].astype("float64")
            valid = ~np.isnan(a)
            pad = lambda x: np.pad(np.cumsum(np.cumsum(x, 0), 1), ((1, 0), (1, 0)))
            self._sat[layer] = (pad(np.where(valid, a, 0.0)), pad(valid.astype("float64")))
        return self._sat[layer]

    def window(self, layer, lat, lon, radius_m, how):
        rows, cols = self.shape
        r = np.floor((self.lat_max - np.asarray(lat, dtype=float)) / self.res).astype(int)
        c = np.floor((np.asarray(lon, dtype=float) - self.lon_min) / self.res).astype(int)
        inside = (r >= 0) & (r < rows) & (c >= 0) & (c < cols)
        ky, kx = int(round(radius_m / self.cell_y_m)), int(round(radius_m / self.cell_x_m))
        r0, r1 = np.clip(r - ky, 0, rows), np.clip(r + ky + 1, 0, rows)
        c0, c1 = np.clip(c - kx, 0, cols), np.clip(c + kx + 1, 0, cols)
        s, n = self._tables(layer)
        box = lambda t: t[r1, c1] - t[r0, c1] - t[r1, c0] + t[r0, c0]
        total, count = box(s), box(n)
        with np.errstate(invalid="ignore", divide="ignore"):
            val = total if how == "sum" else total / count
        val = np.where(inside & (count > 0), val, np.nan)
        return val


def context_features(lat, lon, grid) -> pd.DataFrame:
    lat = np.atleast_1d(np.asarray(lat, dtype=float))
    lon = np.atleast_1d(np.asarray(lon, dtype=float))
    out = {}
    for name, layer, radius, how in CONTEXT_SPEC:
        if grid is None or layer not in grid.layers:
            out[name] = np.full(len(lat), np.nan)
        else:
            out[name] = np.round(grid.window(layer, lat, lon, radius, how), 4)
    if grid is None:
        warnings.warn("context grid not found: run scripts/fetch_context_data.py then run_pipeline.py --step context")
    return pd.DataFrame(out)
