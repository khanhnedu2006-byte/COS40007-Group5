"""Baseline models.   Owner: Person 2

Baseline 1, KNN: location only (input in degrees, haversine distance).
Baseline 2, Random Forest: same features as the main model EXCEPT theory_mbps (no physics).
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.neighbors import KNeighborsRegressor

from speedmap import config
from speedmap.models.base import BaseSpeedModel


class KNNBaseline(BaseSpeedModel):
    """Predict speed from distinct nearby measured locations."""

    name = "knn"

    def __init__(self, n_neighbors: int = 10):
        """Create an equal-weight geographic KNN regressor.

        @param n_neighbors: Positive number of distinct locations to average.
        @type n_neighbors: int
        """
        self.n_neighbors = n_neighbors
        self.columns = ["latitude", "longitude"]
        self.model = KNeighborsRegressor(
            n_neighbors=n_neighbors,
            weights="uniform",
            algorithm="ball_tree",
            metric="haversine",
        )

    def fit(
        self,
        X: pd.DataFrame,
        y: np.ndarray,
        sample_weight: np.ndarray | None = None,
    ) -> "KNNBaseline":
        """Fit one test-count-weighted target per coordinate pair.

        Repeated tile-quarter rows are combined first, preventing the same
        physical location from occupying several neighbour positions.

        @param X: Rows containing ``latitude`` and ``longitude`` in degrees.
        @type X: pandas.DataFrame
        @param y: Download speeds in Mbps, one per row of X.
        @type y: numpy.ndarray
        @param sample_weight: Optional positive weights used only when repeated
            observations at one location are combined. Passing the ``tests``
            column gives better-supported measurements more influence.
        @type sample_weight: numpy.ndarray or None
        @return: This fitted model.
        @rtype: KNNBaseline
        """
        coordinates = X[["latitude", "longitude"]].to_numpy(dtype=float)
        targets = np.asarray(y, dtype=float)
        weights = (
            np.ones(len(X), dtype=float)
            if sample_weight is None
            else np.asarray(sample_weight, dtype=float)
        )
        if targets.ndim != 1 or weights.ndim != 1:
            raise ValueError("y and sample_weight must be one-dimensional")
        if len(targets) != len(X) or len(weights) != len(X):
            raise ValueError("X, y and sample_weight must have the same number of rows")
        if not np.isfinite(coordinates).all() or not np.isfinite(targets).all():
            raise ValueError("Coordinates and targets must be finite")
        if not np.isfinite(weights).all() or (weights <= 0).any():
            raise ValueError("sample_weight values must be finite and positive")

        rows = pd.DataFrame(coordinates, columns=["latitude", "longitude"])
        rows["weighted_target"] = targets * weights
        rows["weight"] = weights
        locations = rows.groupby(
            ["latitude", "longitude"], sort=True, as_index=False
        ).sum()
        if len(locations) < self.n_neighbors:
            raise ValueError(
                "n_neighbors cannot exceed the number of distinct training locations"
            )

        speeds = locations["weighted_target"] / locations["weight"]
        # Scikit-learn's haversine metric expects [latitude, longitude] radians.
        coordinates_rad = np.radians(
            locations[["latitude", "longitude"]].to_numpy()
        )
        self.model.fit(coordinates_rad, speeds.to_numpy())
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predict download speeds for locations expressed in degrees.

        @param X: Rows containing ``latitude`` and ``longitude``.
        @type X: pandas.DataFrame
        @return: Predicted download speeds in Mbps.
        @rtype: numpy.ndarray
        """
        coordinates_rad = np.radians(
            X[["latitude", "longitude"]].to_numpy(dtype=float)
        )
        return self.model.predict(coordinates_rad)

    def get_params(self) -> dict:
        """Return settings recorded with the saved model artifact."""
        return {
            "n_neighbors": self.n_neighbors,
            "weights": "uniform",
            "metric": "haversine",
        }


class RandomForestBaseline(BaseSpeedModel):
    """Predict download speed from non-physics spatial and tower features.

    This baseline deliberately excludes ``theory_mbps``. Its purpose is to
    show what a standard machine-learning model achieves before the 3GPP
    physics estimate is added by the hybrid model.
    """

    name = "random_forest"

    def __init__(self, n_estimators: int = 300, min_samples_leaf: int = 5):
        """Create a reproducible Random Forest regressor.

        @param n_estimators: Positive number of decision trees in the forest.
        @type n_estimators: int
        @param min_samples_leaf: Minimum training rows in each leaf. Larger
            values smooth predictions and reduce very local overfitting.
        @type min_samples_leaf: int
        """
        self.n_estimators = n_estimators
        self.min_samples_leaf = min_samples_leaf
        self.columns = [c for c in config.FEATURE_COLUMNS if c != "theory_mbps"]
        # Fitted separately in each CV fold; retain all-empty context columns as zeros.
        self.imputer = SimpleImputer(strategy="median", keep_empty_features=True)
        self.model = RandomForestRegressor(
            n_estimators=n_estimators,
            min_samples_leaf=min_samples_leaf,
            random_state=config.RANDOM_SEED,
            n_jobs=-1,
        )

    def fit(
        self,
        X: pd.DataFrame,
        y: np.ndarray,
        sample_weight: np.ndarray | None = None,
    ) -> "RandomForestBaseline":
        """Fit the forest using the configured non-physics feature columns.

        @param X: Training table containing every column in ``self.columns``.
        @type X: pandas.DataFrame
        @param y: Download speeds in Mbps, one per row of X.
        @type y: numpy.ndarray
        @param sample_weight: Optional non-negative influence of each row. The
            project passes ``sample_weight = sqrt(tests)`` so measurements
            supported by more Ookla tests receive more influence.
        @type sample_weight: numpy.ndarray or None
        @return: This fitted model.
        @rtype: RandomForestBaseline
        """
        features = self._features(X)
        targets = np.asarray(y, dtype=float)
        weights = (
            None
            if sample_weight is None
            else np.asarray(sample_weight, dtype=float)
        )
        if len(targets) != len(features):
            raise ValueError("X and y must have the same number of rows")
        if weights is not None and len(weights) != len(features):
            raise ValueError("X and sample_weight must have the same number of rows")
        if not np.isfinite(targets).all():
            raise ValueError("Targets must be finite")
        if weights is not None and (
            not np.isfinite(weights).all() or (weights < 0).any()
        ):
            raise ValueError("sample_weight values must be finite and non-negative")

        self.model.fit(self.imputer.fit_transform(features), targets, sample_weight=weights)
        return self

    def _features(self, X: pd.DataFrame) -> pd.DataFrame:
        features = X[self.columns]
        required = [c for c in self.columns if c not in config.CONTEXT_FEATURES]
        if not np.isfinite(features[required].to_numpy(dtype=float)).all():
            raise ValueError("Random Forest required features must be finite and non-missing")
        if np.isinf(features.to_numpy(dtype=float)).any():
            raise ValueError("Random Forest features must not contain infinity")
        return features

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predict download speed from non-physics feature columns.

        @param X: Rows containing the same named columns used during fitting.
        @type X: pandas.DataFrame
        @return: Predicted download speeds in Mbps.
        @rtype: numpy.ndarray
        """
        return self.model.predict(self.imputer.transform(self._features(X)))

    def get_params(self) -> dict:
        """Return the settings stored alongside the model artifact."""
        return {
            "n_estimators": self.n_estimators,
            "min_samples_leaf": self.min_samples_leaf,
            "random_state": config.RANDOM_SEED,
            "context_imputation": "training median; all-empty columns use zero",
        }
