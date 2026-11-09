"""Run: pytest tests/test_features.py   (Person 1)"""
import numpy as np
import pytest
import pandas as pd

from speedmap import config
from speedmap.features.spatial import TowerIndex
from speedmap.features.point_features import PointFeaturizer
from speedmap.features.tower_features import tower_features

TOWERS = pd.DataFrame({
    "tower_id": [1, 2, 3],
    "latitude": [21.0285, 21.0300, 21.1000],
    "longitude": [105.8542, 105.8560, 105.9000],
})


CELLS = pd.DataFrame({
    "latitude": [21.0285, 21.0290, 21.0300],
    "longitude": [105.8542, 105.8545, 105.8560],
    "operator": [1, 2, 4],
})
TILES = pd.DataFrame({
    "quadkey": ["a", "b"],
    "latitude": [21.0290, 21.0400],
    "longitude": [105.8550, 105.8600],
    "devices": [50, 10],
})


def test_tower_columns():
    feats = tower_features(np.array([21.0285]), np.array([105.8542]), TowerIndex(TOWERS))
    assert list(feats.columns) == ["latitude", "longitude"] + config.TOWER_FEATURES


def test_point_features_match_contract():
    feats = PointFeaturizer(TOWERS, CELLS, TILES).features([21.0285], [105.8542])
    assert list(feats.columns) == config.FEATURE_COLUMNS
    assert feats["operators_1km"].iloc[0] == 3
    assert feats["cells_1km"].iloc[0] == 3
    assert feats["center_km"].iloc[0] < 0.01


def test_activity_counts_neighbours_not_self():
    feats = PointFeaturizer(TOWERS, CELLS, TILES).features([21.0285], [105.8542])
    # điểm không nằm trong ô "a"/"b" (quadkey khác) -> own_devices = 0, ô lân cận 1 km có 50 thiết bị
    assert feats["own_devices"].iloc[0] == 0
    assert feats["devices_1km"].iloc[0] == pytest.approx(np.log1p(50), abs=1e-3)


def test_nearest_distance_is_small_next_to_tower():
    feats = tower_features(np.array([21.0285]), np.array([105.8542]), TowerIndex(TOWERS))
    assert feats["dist_nearest_tower_m"].iloc[0] < 5


def test_far_point_keeps_true_distance():
    # Điểm ở ngoại thành: khoảng cách thật (> bán kính tìm kiếm), không có trạm trong 1 km
    feats = tower_features(np.array([20.6]), np.array([105.3]), TowerIndex(TOWERS))
    assert feats["dist_nearest_tower_m"].iloc[0] > config.TOWER_SEARCH_RADIUS_M
    assert feats["towers_1km"].iloc[0] == 0
