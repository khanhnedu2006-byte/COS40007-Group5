"""Split conformal prediction intervals for individual tile speeds."""

import numpy as np

from speedmap import config


class ConformalInterval:
    def __init__(self, level: float = config.CONFIDENCE_LEVEL):
        if not 0 < level < 1:
            raise ValueError("level must be between zero and one")
        self.level = level
        self.q = None

    def calibrate(self, y_true: np.ndarray, y_pred: np.ndarray):
        true, pred = np.asarray(y_true, dtype=float), np.asarray(y_pred, dtype=float)
        if (
            true.ndim != 1
            or true.shape != pred.shape
            or not len(true)
            or not np.isfinite(true).all()
            or not np.isfinite(pred).all()
        ):
            raise ValueError(
                "Calibration values must be non-empty, aligned and finite vectors"
            )
        scores = np.abs(true - pred)
        rank = int(np.ceil((len(scores) + 1) * self.level))
        if rank > len(scores):
            raise ValueError(
                "Not enough calibration observations for the requested level"
            )
        self.q = float(np.partition(scores, rank - 1)[rank - 1])
        return self

    def interval(self, y_pred: np.ndarray):
        if self.q is None:
            raise ValueError("Calibrate the interval first")
        pred = np.asarray(y_pred, dtype=float)
        if not np.isfinite(pred).all():
            raise ValueError("Predictions must be finite")
        return np.maximum(0, pred - self.q), pred + self.q
