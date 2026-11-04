"""Spatial estimates from the current observed Ookla tiles, without a trained model."""
import numpy as np
from sklearn.neighbors import BallTree

from speedmap import config
from speedmap.data.catalog import (
    data_fingerprints,
    file_digest,
    load_tile_table,
    load_tower_table,
)
from speedmap.features.spatial import EARTH_RADIUS_M, TowerIndex


class DataPredictor:
    tower_data_source = "dataset"

    def __init__(self):
        self.towers = load_tower_table()
        self.tiles = load_tile_table()
        self.index = TowerIndex(self.towers)
        self.tile_index = BallTree(np.radians(self.tiles[["latitude", "longitude"]].to_numpy()), metric="haversine")
        self.version = "ookla-spatial-v1-" + file_digest(config.TILES_FILE)[:12]
        self.data_period = str(self.tiles["last_quarter"].max())
        self.observation_count = len(self.tiles)
        self.data_fingerprints = data_fingerprints()

    def tower_list(self):
        return self.towers.to_dict(orient="records")

    def predict(self, lat, lon):
        distance, indices = self.tile_index.query(np.radians([[lat, lon]]), k=min(5, len(self.tiles)))
        distance = distance[0] * EARTH_RADIUS_M
        nearby = self.tiles.iloc[indices[0]]
        weights = np.sqrt(nearby["tests"].to_numpy(dtype=float)) / np.maximum(distance, 25) ** 2
        if distance[0] < 1:
            weights[:] = 0
            weights[0] = 1  # Preserve recorded values at the exact tile centre.
        weights /= weights.sum()
        if distance[0] < 1:
            download, upload, latency = (float(nearby.iloc[0][column]) for column in ["download_mbps", "upload_mbps", "latency_ms"])
        else:
            download = float(np.expm1(np.average(np.log1p(nearby["download_mbps"]), weights=weights)))
            upload = float(np.expm1(np.average(np.log1p(nearby["upload_mbps"]), weights=weights)))
            latency = float(np.average(nearby["latency_ms"], weights=weights))
        return {
            "latitude": lat, "longitude": lon, "download_mbps": download,
            "download_low": min(download, float(nearby["download_mbps"].min())),
            "download_high": max(download, float(nearby["download_mbps"].max())),
            "upload_mbps": upload, "latency_ms": latency,
            "quality_level": config.quality_level(download),
            "theory_mbps": None, "local_effect_mbps": None,
            "nearest_towers": self.index.nearest(lat, lon, config.NEAREST_TOWERS_IN_POPUP).to_dict(orient="records"),
            "source": "data", "model_version": self.version,
            "interval_kind": "neighbour_spread", "confidence_level": None,
            "data_support": {"tiles_used": len(nearby), "tests": int(nearby["tests"].sum()),
                             "nearest_tile_distance_m": round(float(distance[0]), 1),
                             "latest_quarter": str(nearby["last_quarter"].max())},
        }
