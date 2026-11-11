"""Evaluation metrics.   Owner: Person 2"""
from sklearn.metrics import accuracy_score, mean_absolute_error, root_mean_squared_error

from speedmap import config


def mae(y_true, y_pred) -> float:
    return float(mean_absolute_error(y_true, y_pred))


def rmse(y_true, y_pred) -> float:
    return float(root_mean_squared_error(y_true, y_pred))


def level_accuracy(y_true, y_pred) -> float:
    """Share of points whose quality level (config.quality_level) is predicted correctly."""
    return float(accuracy_score(
        [config.quality_level(value) for value in y_true],
        [config.quality_level(value) for value in y_pred],
    ))


def coverage(y_true, low, high) -> float:
    """Share of true values inside [low, high]. Target: 0.75 to 0.85 for an 80% range."""
    # TODO
    raise NotImplementedError


def all_metrics(y_true, y_pred) -> dict:
    return {"mae": mae(y_true, y_pred), "rmse": rmse(y_true, y_pred), "level_accuracy": level_accuracy(y_true, y_pred)}
