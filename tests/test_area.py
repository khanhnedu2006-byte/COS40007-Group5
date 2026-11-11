"""Run: pytest tests/test_area.py   (Person 1)"""
import numpy as np
import pandas as pd
import pytest

from speedmap import config
from speedmap.evaluation.area import area_level_scores
from speedmap.inference.area import AreaSampler, area_estimate, weighted_log_mean

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


def test_no_supported_areas_returns_explicit_missing_metrics():
    scores = area_level_scores(TILES.assign(tests=1), np.ones(len(TILES)), min_tests=30)
    assert scores["n_areas"] == 0 and scores["share_of_clicks_evaluated"] == 0
    assert scores["mae_mbps"] is None and scores["level_accuracy"] is None


@pytest.mark.parametrize("predictions", [np.ones(7), np.full(8, np.nan), np.full(8, -1), np.ones((8, 1))])
def test_invalid_scoring_predictions_are_rejected(predictions):
    with pytest.raises(ValueError):
        area_level_scores(TILES, predictions)


def test_regional_score_pools_all_tiles_before_scoring():
    tiles = TILES.iloc[:2].copy()
    truth = weighted_log_mean(tiles.download_mbps, tiles.tests)
    pred = weighted_log_mean([10, 200], tiles.tests)
    scores = area_level_scores(tiles, [10, 200], min_tests=30)
    assert scores['mae_mbps'] == pytest.approx(abs(truth - pred))
    assert scores['n_areas'] == 2


def test_dense_and_empty_regions_report_actual_sampling_support():
    class Featurizer:
        def features(self, lat, lon):
            return pd.DataFrame({'latitude': lat, 'longitude': lon})

    sampler = AreaSampler(TILES)
    def predict(X):
        return np.full(len(X), 100.)
    dense = area_estimate(predict, Featurizer(), sampler, 21.0285, 105.8542, radius_m=1500)
    assert dense['area_points'] == dense['area_ookla_tiles'] == 7
    assert dense['area_grid_points'] == 0
    assert dense['area_quality_level'] == 'Good'
    empty = area_estimate(predict, Featurizer(), sampler, 20.8, 105.8)
    assert empty['area_ookla_tiles'] == 0
    assert empty['area_points'] == empty['area_grid_points'] > 0


def test_nonfinite_inference_cannot_be_hidden_by_pooling():
    with pytest.raises(ValueError, match='finite'):
        weighted_log_mean([np.nan, 100], [1, 2])
