"""Serve the regional baseline winner using the same features as training."""
import numpy as np
import pandas as pd

from speedmap import config
from speedmap.artifacts import load_model
from speedmap.data.catalog import load_tower_table, verify_fingerprints
from speedmap.data.towers import load_cells
from speedmap.features.point_features import PointFeaturizer
from speedmap.inference.area import AreaSampler, area_estimate


def load_tiles() -> pd.DataFrame:
    return pd.read_csv(config.TILES_FILE, dtype={"quadkey": str})


class Predictor:
    def __init__(self, model_name: str = "regional", run_id: str | None = None):
        self.bundle, self.metadata = load_model(model_name, run_id)
        if not isinstance(self.bundle, dict) or self.bundle.get("kind") != "regional_baseline":
            raise ValueError("Saved bundle must be a regional_baseline; run scripts/train_baselines.py")
        self.model = self.bundle["model"]
        self.model_name = self.bundle["model_name"]
        self.columns = self.metadata["feature_columns"]
        expected = (["latitude", "longitude"] if self.model_name == "knn" else
                    [c for c in config.FEATURE_COLUMNS if c != "theory_mbps"])
        if self.model_name not in {"knn", "random_forest"} or self.columns != expected:
            raise ValueError("Saved model feature columns differ from the baseline feature contract")
        # Historical reports keep the bundle radius; serving follows the app setting.
        self.evaluation_radius_m = float(self.bundle["area_radius_m"])
        self.radius_m = float(config.AREA_RADIUS_M)
        if not np.isfinite(self.evaluation_radius_m) or self.evaluation_radius_m <= 0:
            raise ValueError("Saved area radius must be finite and positive")
        fingerprints = self.metadata.get("data_fingerprints")
        if fingerprints is None:
            # Regional runs saved before the main-branch provenance contract already
            # record equivalent input hashes. Verify those rather than accepting stale data.
            hashes = {key.replace("\\", "/"): value for key, value in
                      self.metadata.get("provenance", {}).get("input_sha256", {}).items()}
            fingerprints = {name: hashes[path.relative_to(config.ROOT).as_posix()]
                            for name, path in {"towers": config.TOWERS_FILE, "tiles": config.TILES_FILE,
                                               "boundary": config.HANOI_BOUNDARY_FILE}.items()
                            if path.is_relative_to(config.ROOT) and path.relative_to(config.ROOT).as_posix() in hashes}
        verify_fingerprints(fingerprints)
        self.data_fingerprints = fingerprints
        self.towers = load_tower_table()
        tiles = load_tiles()
        self.featurizer = PointFeaturizer(self.towers, load_cells(), tiles, include_physics=False)
        self.area_sampler = AreaSampler(tiles)
        self.index = self.featurizer.tower_index
        self.version = str(self.metadata["run_id"])
        self.predict(*config.HANOI_CENTER)

    def predict_area(self, lat: float, lon: float) -> dict:
        return area_estimate(self.model.predict, self.featurizer, self.area_sampler,
                             lat, lon, self.columns, self.radius_m)

    def predict(self, lat: float, lon: float) -> dict:
        return {
            "latitude": lat, "longitude": lon, **self.predict_area(lat, lon),
            "nearest_towers": self.index.nearest(lat, lon, config.NEAREST_TOWERS_IN_POPUP)[
                ["tower_id", "latitude", "longitude", "distance_m", "source"]
            ].to_dict(orient="records"),
            "source": "model", "model_name": self.model_name, "model_version": self.version,
        }

    def tower_list(self) -> list:
        return self.towers[["tower_id", "latitude", "longitude", "source"]].to_dict(orient="records")
