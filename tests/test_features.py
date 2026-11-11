"""Run: pytest tests/test_features.py   (Person 1)"""
import numpy as np
import pytest
import pandas as pd

from speedmap import config
from speedmap.features.spatial import TowerIndex
from speedmap.features.point_features import PointFeaturizer
from speedmap.features.tower_features import tower_features
from speedmap.features.build import build_tile_table, build_training_table, validate_training_table

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


def test_baseline_tables_skip_unfinished_physics_and_keep_feature_contract(monkeypatch):
    import warnings

    def unexpected_physics(*args):
        raise AssertionError("Baseline feature generation must not call physics")

    monkeypatch.setattr("speedmap.features.tower_features.theory_for_points", unexpected_physics)
    clean = pd.DataFrame({
        "quadkey": ["001", "001", "002"], "latitude": [21.029, 21.029, 21.04],
        "longitude": [105.855, 105.855, 105.86], "quarter": ["2026-2", "2026-3", "2026-3"],
        "quarter_index": [8105, 8106, 8106], "download_mbps": [80., 120., 50.],
        "upload_mbps": [20., 30., 15.], "latency_ms": [20., 18., 30.],
        "tests": [10, 20, 5], "devices": [5, 10, 3],
    })
    with warnings.catch_warnings():
        warnings.filterwarnings("error", message=".*(physics|theory_mbps).*")
        tiles = build_tile_table(clean, TOWERS, CELLS, include_physics=False)
        train = build_training_table(clean, TOWERS, CELLS, tiles, include_physics=False)
        validate_training_table(tiles, include_physics=False)
        feats = PointFeaturizer(TOWERS, CELLS, tiles, include_physics=False).features([21.0285], [105.8542])
    assert len(tiles) == 2 and len(train) == 3
    assert tiles["quadkey"].tolist() == ["001", "002"]
    assert list(feats.columns) == config.FEATURE_COLUMNS
    for frame in (tiles, train, feats):
        assert frame["theory_mbps"].isna().all()
        assert frame["dist_nearest_tower_m"].notna().all()
    with pytest.raises(ValueError, match="Missing columns"):
        validate_training_table(tiles.drop(columns="towers_1km"), include_physics=False)
    # Physics-enabled callers still receive the existing missing-theory warning.
    with pytest.warns(UserWarning, match="theory_mbps is empty"):
        validate_training_table(tiles)


def test_explicit_physics_features_still_report_unfinished_module(monkeypatch):
    def unfinished(*args):
        raise NotImplementedError

    monkeypatch.setattr("speedmap.features.tower_features.theoretical_speed_mbps", unfinished)
    with pytest.warns(UserWarning, match="physics.link_budget is not implemented"):
        feats = tower_features(np.array([21.0285]), np.array([105.8542]), TowerIndex(TOWERS))
    assert feats["theory_mbps"].isna().all()


@pytest.mark.parametrize("include_physics", [False, True])
def test_pipeline_physics_is_an_explicit_opt_in(monkeypatch, include_physics):
    import sys

    from scripts import run_pipeline

    called = []
    monkeypatch.setattr(run_pipeline, "STEPS", {"features": lambda **kwargs: called.append(kwargs)})
    monkeypatch.setattr(sys, "argv", ["run_pipeline.py", "--step", "features"]
                        + (["--include-physics"] if include_physics else []))
    run_pipeline.main()
    assert called == [{"include_physics": include_physics}]
