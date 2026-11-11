"""Run: pytest tests/test_area.py   (Person 1)"""
import numpy as np
import pandas as pd
import pytest

from speedmap import config
from speedmap.evaluation.area import area_level_scores
from speedmap.inference.area import AreaSampler, weighted_log_mean

TILES = pd.DataFrame({
    "quadkey": [str(i) for i in range(8)],
    "latitude": [21.0285 + 0.002 * i for i in range(7)] + [21.30],
    "longitude": [105.8542] * 7 + [105.60],
    "tests": [10, 20, 5, 5, 5, 5, 5, 50],
    "download_mbps": [120, 80, 150, 90, 110, 130, 100, 20],
})


def test_tiles_inside_radius_are_used_with_test_weights():
    pts = AreaSampler(TILES).points(21.0285, 105.8542)
    assert (pts["source"] == "ookla_tile").sum() == 3  # Only the first three tile centres are within 500 m.
    assert pts.loc[pts["source"] == "ookla_tile", "weight"].sum() == 35


def test_sparse_area_adds_grid_points():
    pts = AreaSampler(TILES).points(21.30, 105.60)               # chỉ 1 ô Ookla trong vùng
    assert (pts["source"] == "grid").sum() == 9
    assert np.hypot((pts.latitude - 21.30) * 110_570, (pts.longitude - 105.60) * 103_900).max() <= config.AREA_RADIUS_M + 50


def test_weighted_log_mean():
    assert weighted_log_mean([100, 100], [1, 5]) == pytest.approx(100)
    assert 40 < weighted_log_mean([10, 160], [1, 1]) < 85


def test_perfect_predictions_score_100_percent():
    s = area_level_scores(TILES, TILES["download_mbps"], min_tests=10)
    assert s["level_accuracy"] == 1.0 and s["mae_mbps"] == pytest.approx(0)
