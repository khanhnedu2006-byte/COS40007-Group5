"""Deterministic UI fixtures, independent of the team's training and physics code.

All towers, speeds and ranges here are simulated. Nothing is a real measurement.
"""
import math

import numpy as np
import pandas as pd

from speedmap import config
from speedmap.data.boundary import contains
from speedmap.features.spatial import TowerIndex


class DemoPredictor:
    version = "demo-v1"

    def __init__(self):
        rng = np.random.default_rng(42)
        lat = np.concatenate([rng.normal(21.035, 0.045, 180), rng.uniform(20.65, 21.3, 180)])
        lon = np.concatenate([rng.normal(105.81, 0.055, 180), rng.uniform(105.45, 106.03, 180)])
        keep = contains(lat, lon)
        self.towers = pd.DataFrame({"latitude": lat[keep], "longitude": lon[keep]}).round(6)
        self.towers.insert(0, "tower_id", [f"DEMO-{i + 1:03}" for i in range(len(self.towers))])
        self.towers["source"] = "simulated"
        self.index = TowerIndex(self.towers)

    def tower_list(self):
        return self.towers.to_dict(orient="records")

    def predict(self, lat: float, lon: float):
        nearest = self.index.nearest(lat, lon, config.NEAREST_TOWERS_IN_POPUP)
        distance = float(nearest.iloc[0]["distance_m"])
        wave = math.sin((lat - 21) * 90) * math.cos((lon - 105.8) * 70)
        download = round(max(8, 180 + 75 * wave - min(distance / 55, 140)), 1)
        width = round(20 + min(distance / 100, 65), 1)
        theory = round(download + 35 + 12 * math.sin(lat * 50), 1)
        return {
            "latitude": lat, "longitude": lon, "download_mbps": download,
            "download_low": round(max(0, download - width), 1),
            "download_high": round(download + width, 1),
            "upload_mbps": round(download * 0.23 + 3, 1),
            "latency_ms": round(16 + distance / 400 + 5 * (1 - wave), 1),
            "quality_level": config.quality_level(download),
            "theory_mbps": theory, "local_effect_mbps": round(download - theory, 1),
            "nearest_towers": nearest.to_dict(orient="records"),
            "source": "demo", "model_version": self.version,
            "interval_kind": "illustrative", "confidence_level": None,
        }
