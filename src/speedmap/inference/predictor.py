"""Adapter for the model team's saved bundle and shared feature pipeline."""
import numpy as np

from speedmap import config
from speedmap.artifacts import load_model
from speedmap.data.towers import load_towers
from speedmap.features.spatial import TowerIndex
from speedmap.features.tower_features import tower_features


class Predictor:
    def __init__(self, model_name: str = "hybrid", run_id: str | None = None):
        self.bundle, self.metadata = load_model(model_name, run_id)
        required = {"model", "conformal", "secondary", "latest_quarter_index"}
        if not isinstance(self.bundle, dict) or not required.issubset(self.bundle):
            raise ValueError(f"Saved bundle must include {sorted(required)}.")
        if not set(config.SECONDARY_TARGETS).issubset(self.bundle["secondary"]):
            raise ValueError("Saved bundle must include upload and latency estimators.")
        self.columns = self.metadata.get("feature_columns", list(config.FEATURE_COLUMNS))
        if self.columns != list(config.FEATURE_COLUMNS):
            raise ValueError("Saved model feature columns differ from the shared feature contract.")
        self.towers = load_towers()
        required_towers = {"tower_id", "latitude", "longitude"}
        if self.towers.empty or not required_towers.issubset(self.towers.columns):
            raise ValueError("Tower table is empty or missing required columns.")
        if not np.isfinite(self.towers[["latitude", "longitude"]].to_numpy()).all():
            raise ValueError("Tower coordinates must be finite.")
        if "source" not in self.towers:
            self.towers = self.towers.assign(source="estimated")
        self.index = TowerIndex(self.towers)
        self.version = str(self.metadata["run_id"])
        self.predict(*config.HANOI_CENTER)

    def predict(self, lat: float, lon: float) -> dict:
        features = tower_features(np.array([lat]), np.array([lon]), self.index)
        features["quarter_index"] = self.bundle["latest_quarter_index"]
        features = features[self.columns]
        if not np.isfinite(features.to_numpy(dtype=float)).all():
            raise ValueError("Shared features contain non-finite values; check the physics implementation.")
        download = float(np.asarray(self.bundle["model"].predict(features)).reshape(-1)[0])
        low, high = self.bundle["conformal"].interval(np.array([download]))
        secondary = {
            name: float(np.asarray(self.bundle["secondary"][name].predict(features)).reshape(-1)[0])
            for name in config.SECONDARY_TARGETS
        }
        theory = float(features["theory_mbps"].iloc[0])
        result = {
            "latitude": lat, "longitude": lon, "download_mbps": download,
            "download_low": float(np.asarray(low).reshape(-1)[0]),
            "download_high": float(np.asarray(high).reshape(-1)[0]),
            **secondary, "quality_level": config.quality_level(download),
            "theory_mbps": theory, "local_effect_mbps": download - theory,
            "nearest_towers": self.index.nearest(lat, lon, config.NEAREST_TOWERS_IN_POPUP)[
                ["tower_id", "latitude", "longitude", "distance_m", "source"]
            ].to_dict(orient="records"),
            "source": "model", "model_version": self.version,
            "interval_kind": "conformal", "confidence_level": config.CONFIDENCE_LEVEL,
        }
        numbers = [result[key] for key in (
            "download_mbps", "download_low", "download_high", "upload_mbps", "latency_ms", "theory_mbps",
        )]
        if not np.isfinite(numbers).all() or min(numbers) < 0:
            raise ValueError("Model outputs must be finite, non-negative numbers.")
        if not result["download_low"] <= download <= result["download_high"]:
            raise ValueError("Conformal range must contain the estimate.")
        return result

    def tower_list(self) -> list:
        return self.towers[["tower_id", "latitude", "longitude", "source"]].to_dict(orient="records")
