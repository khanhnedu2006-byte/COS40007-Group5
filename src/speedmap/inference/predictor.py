"""Serve the regional baseline winner using the same features as training."""

import numpy as np
import pandas as pd

from speedmap import config
from speedmap.artifacts import load_model
from speedmap.data.towers import load_cells
from speedmap.data.catalog import load_tower_table, verify_fingerprints
from speedmap.features.point_features import PointFeaturizer
from speedmap.inference.area import AreaSampler, area_estimate


def load_tiles() -> pd.DataFrame:
    return pd.read_csv(config.TILES_FILE, dtype={"quadkey": str})


class Predictor:
    def __init__(self, model_name: str = "regional", run_id: str | None = None):
        self.bundle, self.metadata = load_model(model_name, run_id)
        if not isinstance(self.bundle, dict) or self.bundle.get("kind") not in {
            "regional_baseline",
            "regional_model",
        }:
            raise ValueError(
                "Saved bundle must be a regional_baseline; run python -m speedmap.cli.train_baselines"
            )
        self.model = self.bundle["model"]
        self.model_name = self.bundle["model_name"]
        self.models = self.bundle.get("models", {self.model_name: self.model})
        self.columns = self.metadata["feature_columns"]
        contracts = {
            "knn": ["latitude", "longitude"],
            "random_forest": [c for c in config.FEATURE_COLUMNS if c != "theory_mbps"],
            "xgboost_only": [c for c in config.FEATURE_COLUMNS if c != "theory_mbps"],
            "hybrid": list(config.FEATURE_COLUMNS),
            "physics_only": ["theory_mbps"],
        }
        if (
            self.model_name not in contracts
            or self.columns != contracts[self.model_name]
        ):
            raise ValueError(
                "Saved model feature columns differ from the baseline feature contract"
            )
        if self.model_name not in self.models or any(
            name not in contracts
            or list(getattr(model, "columns", [])) != contracts[name]
            for name, model in self.models.items()
        ):
            raise ValueError(
                "Saved model feature columns differ from the regional feature contract"
            )
        self.radius_m = float(self.bundle["area_radius_m"])
        if not np.isfinite(self.radius_m) or self.radius_m <= 0:
            raise ValueError("Saved area radius must be finite and positive")
        fingerprints = self.metadata.get("data_fingerprints")
        if fingerprints is None:
            # Regional runs saved before the main-branch provenance contract already
            # record equivalent input hashes. Verify those rather than accepting stale data.
            hashes = self.metadata.get("provenance", {}).get("input_sha256", {})
            fingerprints = {
                name: hashes[str(path.relative_to(config.ROOT))]
                for name, path in {
                    "towers": config.TOWERS_FILE,
                    "tiles": config.TILES_FILE,
                    "boundary": config.HANOI_BOUNDARY_FILE,
                }.items()
                if path.is_relative_to(config.ROOT)
                and str(path.relative_to(config.ROOT)) in hashes
            }
        verify_fingerprints(fingerprints)
        self.data_fingerprints = fingerprints
        self.towers = load_tower_table()
        tiles = load_tiles()
        self.featurizer = PointFeaturizer(
            self.towers,
            load_cells(),
            tiles,
            include_physics=bool(self.models.keys() & {"hybrid", "physics_only"}),
        )
        self.area_sampler = AreaSampler(tiles)
        self.index = self.featurizer.tower_index
        self.version = str(self.metadata["run_id"])
        self.predict(*config.HANOI_CENTER)

    def available_models(self):
        return {"default": self.model_name, "models": list(self.models)}

    def predict_area(
        self, lat: float, lon: float, model_name: str | None = None
    ) -> dict:
        model = self.models[model_name or self.model_name]
        return area_estimate(
            model.predict,
            self.featurizer,
            self.area_sampler,
            lat,
            lon,
            model.columns,
            self.radius_m,
        )

    def predict(self, lat: float, lon: float, model_name: str | None = None) -> dict:
        name = model_name or self.model_name
        return {
            "latitude": lat,
            "longitude": lon,
            **self.predict_area(lat, lon, name),
            "nearest_towers": self.index.nearest(
                lat, lon, config.NEAREST_TOWERS_IN_POPUP
            )[["tower_id", "latitude", "longitude", "distance_m", "source"]].to_dict(
                orient="records"
            ),
            "source": "model",
            "model_name": name,
            "model_version": self.version,
        }

    def tower_list(self) -> list:
        return self.towers[["tower_id", "latitude", "longitude", "source"]].to_dict(
            orient="records"
        )
