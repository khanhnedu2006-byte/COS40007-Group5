"""Compatibility imports for the canonical speedmap model implementations."""

from speedmap.models.baselines import (
    KNNBaseline,
    RandomForestBaseline as _RandomForestBaseline,
)
from speedmap.models.conformal import ConformalInterval
from speedmap.models.hybrid import HybridModel, PhysicsOnly, XGBoostOnly


class RandomForestBaseline(_RandomForestBaseline):
    """Legacy import path for the canonical Random Forest."""


MODEL_REGISTRY = {
    "knn": KNNBaseline,
    "random_forest": RandomForestBaseline,
    "hybrid": HybridModel,
    "physics_only": PhysicsOnly,
    "xgboost_only": XGBoostOnly,
}
