"""Physics-guided XGBoost model and ablation models."""

import numpy as np
from xgboost import XGBRegressor

from speedmap import config
from speedmap.models.base import BaseSpeedModel

DEFAULT_XGB_PARAMS = dict(
    n_estimators=600,
    learning_rate=0.03,
    max_depth=6,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=config.RANDOM_SEED,
)


class HybridModel(BaseSpeedModel):
    name = "hybrid"

    def __init__(self, **xgb_params):
        self.params = {**DEFAULT_XGB_PARAMS, **xgb_params}
        self.columns = list(config.FEATURE_COLUMNS)
        self.model = XGBRegressor(**self.params)

    def _features(self, X):
        features = X[self.columns]
        theory = features["theory_mbps"].to_numpy(dtype=float)
        if not np.isfinite(theory).all() or (theory < 0).any():
            raise ValueError(
                "Hybrid model requires finite non-negative theory_mbps; rebuild features with physics"
            )
        if np.isinf(features.to_numpy(dtype=float)).any():
            raise ValueError("Features must not contain infinity")
        return features

    def fit(self, X, y, sample_weight=None):
        features = self._features(X)
        y = np.asarray(y, dtype=float)
        if y.ndim != 1 or len(y) != len(X) or not np.isfinite(y).all() or (y < 0).any():
            raise ValueError("Targets must be aligned, finite and non-negative")
        residual = np.log1p(y) - np.log1p(features["theory_mbps"].to_numpy())
        self.model.fit(features, residual, sample_weight=sample_weight)
        return self

    def correction(self, X) -> np.ndarray:
        return self.model.predict(self._features(X))

    def predict(self, X):
        features = self._features(X)
        return np.maximum(
            0,
            np.expm1(
                np.log1p(features["theory_mbps"].to_numpy())
                + self.model.predict(features)
            ),
        )

    def get_params(self):
        return self.params


class PhysicsOnly(BaseSpeedModel):
    name = "physics_only"
    columns = ["theory_mbps"]

    def fit(self, X, y, sample_weight=None):
        self.predict(X)
        return self

    def predict(self, X):
        result = X["theory_mbps"].to_numpy(dtype=float)
        if not np.isfinite(result).all() or (result < 0).any():
            raise ValueError("Physics model requires finite non-negative theory_mbps")
        return result


class XGBoostOnly(BaseSpeedModel):
    name = "xgboost_only"

    def __init__(self, **xgb_params):
        self.params = {**DEFAULT_XGB_PARAMS, **xgb_params}
        self.columns = [c for c in config.FEATURE_COLUMNS if c != "theory_mbps"]
        self.model = XGBRegressor(**self.params)

    def fit(self, X, y, sample_weight=None):
        y = np.asarray(y, dtype=float)
        if y.ndim != 1 or len(y) != len(X) or not np.isfinite(y).all() or (y < 0).any():
            raise ValueError("Targets must be aligned, finite and non-negative")
        self.model.fit(X[self.columns], np.log1p(y), sample_weight=sample_weight)
        return self

    def predict(self, X):
        return np.maximum(0, np.expm1(self.model.predict(X[self.columns])))

    def get_params(self):
        return self.params
