"""All model features for any list of points. SHARED by training and the backend.   Owner: Person 1

    PointFeaturizer(towers, cells, tiles).features(lat, lon) -> DataFrame with config.FEATURE_COLUMNS

- tower features: distance and number of towers, 3GPP theoretical speed (tower_features.py)
- infrastructure: number of cells within 1 / 2 km, number of operators within 1 km, distance to the centre
- context: population, built-up / trees / cropland / water share, elevation, slope, major roads, POIs
  (data/reference/hanoi_context_grid.npz; NaN until the grid is built)
- activity: Ookla devices of the point's own tile and of the tiles around it (log scale)
  -> a proxy for how many people use the network there. Speeds are never used, so no label leakage.

Backend: build one PointFeaturizer at start-up from hanoi_towers.csv, hanoi_cells.csv and hanoi_tiles.csv.
"""
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

from speedmap import config
from speedmap.data.ookla import tile_quadkey
from speedmap.features.context_features import ContextGrid, context_features
from speedmap.features.spatial import EARTH_RADIUS_M, KM_PER_DEG_LAT, TowerIndex, _radians
from speedmap.features.tower_features import tower_features


def center_km(lat, lon) -> np.ndarray:
    lat0, lon0 = config.HANOI_CENTER
    dy = (np.asarray(lat, dtype=float) - lat0) * KM_PER_DEG_LAT
    dx = (np.asarray(lon, dtype=float) - lon0) * 111.32 * np.cos(np.radians(lat0))
    return np.round(np.hypot(dx, dy), 3)


class PointFeaturizer:
    def __init__(self, towers: pd.DataFrame, cells: pd.DataFrame, tiles: pd.DataFrame,
                 context=None, *, include_physics: bool = True):
        self.include_physics = include_physics
        self.tower_index = TowerIndex(towers)
        self.cells = cells.reset_index(drop=True)
        self.cell_tree = BallTree(_radians(self.cells["latitude"], self.cells["longitude"]), metric="haversine")
        self.cell_operator = self.cells["operator"].to_numpy()
        self.tiles = tiles.reset_index(drop=True)
        self.tile_tree = BallTree(_radians(self.tiles["latitude"], self.tiles["longitude"]), metric="haversine")
        self.tile_devices = self.tiles["devices"].to_numpy(dtype=float)
        self.devices_by_quadkey = dict(zip(self.tiles["quadkey"].astype(str), self.tile_devices))
        self.context = context if context is not None else ContextGrid.load()

    def _infra(self, lat, lon) -> pd.DataFrame:
        pts = _radians(lat, lon)
        out = {f"cells_{r // 1000}km": self.cell_tree.query_radius(pts, r=r / EARTH_RADIUS_M, count_only=True)
               for r in (1000, 2000)}
        idx = self.cell_tree.query_radius(pts, r=1000 / EARTH_RADIUS_M)
        out["operators_1km"] = [len(set(self.cell_operator[ix])) for ix in idx]
        out["center_km"] = center_km(lat, lon)
        return pd.DataFrame(out)

    def _activity(self, lat, lon) -> pd.DataFrame:
        # Ô Ookla chứa điểm: lấy số thiết bị của ô đó; các ô lân cận tính riêng (không gồm ô đó)
        quadkeys = [tile_quadkey(a, b) for a, b in zip(lat, lon)]
        own = np.array([self.devices_by_quadkey.get(q, 0.0) for q in quadkeys])
        pts = _radians(lat, lon)
        out = {"own_devices": np.round(np.log1p(own), 4)}
        for r in config.ACTIVITY_RADII_M:
            idx = self.tile_tree.query_radius(pts, r=r / EARTH_RADIUS_M)
            total = np.array([self.tile_devices[ix].sum() for ix in idx]) - own
            out[f"devices_{r // 1000}km"] = np.round(np.log1p(np.clip(total, 0, None)), 4)
            if r in (1000, 2000):
                has_own = (own > 0).astype(int)
                out[f"tiles_{r // 1000}km"] = np.array([len(ix) for ix in idx]) - has_own
        return pd.DataFrame(out)

    def features(self, lat, lon) -> pd.DataFrame:
        lat = np.atleast_1d(np.asarray(lat, dtype=float))
        lon = np.atleast_1d(np.asarray(lon, dtype=float))
        feats = pd.concat(
            [tower_features(lat, lon, self.tower_index, include_physics=self.include_physics),
             self._infra(lat, lon), self._activity(lat, lon),
             context_features(lat, lon, self.context)], axis=1
        )
        return feats[config.FEATURE_COLUMNS]
