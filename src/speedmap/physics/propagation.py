"""3GPP TR 38.901 urban macro non-line-of-sight path loss."""

import numpy as np

from speedmap import config


def path_loss_db(distance_m: np.ndarray, freq_ghz: float) -> np.ndarray:
    distances = np.asarray(distance_m, dtype=float)
    if (
        not np.isfinite(distances).all()
        or (distances < 0).any()
        or not np.isfinite(freq_ghz)
        or freq_ghz <= 0
    ):
        raise ValueError(
            "Distances must be finite and non-negative and frequency positive"
        )
    return (
        13.54
        + 39.08 * np.log10(np.maximum(distances, config.MIN_DISTANCE_M))
        + 20 * np.log10(freq_ghz)
        - 0.6 * (config.UE_HEIGHT_M - 1.5)
    )
