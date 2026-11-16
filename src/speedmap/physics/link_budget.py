"""Received power, SINR and Shannon capacity for nearby towers."""

import numpy as np

from speedmap import config
from speedmap.physics.propagation import path_loss_db


def dbm_to_mw(dbm):
    return 10 ** (np.asarray(dbm, dtype=float) / 10)


def noise_dbm(bandwidth_mhz: float) -> float:
    if not np.isfinite(bandwidth_mhz) or bandwidth_mhz <= 0:
        raise ValueError("Bandwidth must be finite and positive")
    return float(-174 + 10 * np.log10(bandwidth_mhz * 1e6) + config.NOISE_FIGURE_DB)


def theoretical_speed_mbps(distances_m: np.ndarray) -> float:
    distances = np.asarray(distances_m, dtype=float)
    if distances.ndim != 1:
        raise ValueError("Tower distances must be a one-dimensional vector")
    if not len(distances):
        return 0.0
    params = config.TOWER_PHYSICS
    power = dbm_to_mw(
        params["tx_power_dbm"] - path_loss_db(distances, params["freq_ghz"])
    )
    signal_index = np.argmin(distances)
    signal = power[signal_index]
    interference = np.delete(power, signal_index).sum()
    sinr = signal / (interference + dbm_to_mw(noise_dbm(params["bandwidth_mhz"])))
    return float(
        params["bandwidth_mhz"] * min(np.log2(1 + sinr), config.MAX_SPECTRAL_EFFICIENCY)
    )
