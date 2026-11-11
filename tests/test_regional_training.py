"""Guard spatial held-out evaluation, metric semantics, and regional artifacts."""
import json

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import accuracy_score, mean_absolute_error, root_mean_squared_error

from speedmap import config, training
from speedmap.evaluation.cv import evaluate_baselines, spatial_folds
from speedmap.evaluation.metrics import level_accuracy, mae, rmse
from speedmap.models.baselines import KNNBaseline, RandomForestBaseline


def tile_rows(n=36):
    rows = pd.DataFrame({c: np.ones(n) for c in config.FEATURE_COLUMNS})
    rows['latitude'] = 21.0 + np.arange(n) * 0.001
    rows['longitude'] = 105.85
    rows['quadkey'] = [f'001{i:013d}' for i in range(n)]
    rows['block_id'] = np.repeat(np.arange(6), n // 6)
    rows['tests'] = 40
    rows.loc[0, 'tests'] = 1
    rows['download_mbps'] = 40 + np.arange(n) * 3
    rows['sample_weight'] = np.sqrt(rows['tests'])
    rows['first_quarter'] = '2025-4'
    rows['last_quarter'] = '2026-3'
    rows['theory_mbps'] = np.nan
    rows.index = np.arange(n)[::-1] + 100  # deliberately non-positional index
    return rows


def test_metrics_use_standard_definitions_and_exact_quality_boundaries():
    truth = np.array([14.9, 15, 99.9, 100, 199.9, 200])
    pred = np.array([15, 15, 100, 100, 200, 200])
    assert mae(truth, pred) == mean_absolute_error(truth, pred)
    assert rmse(truth, pred) == root_mean_squared_error(truth, pred)
    assert level_accuracy(truth, pred) == accuracy_score(
        ['Poor', 'Fair', 'Fair', 'Good', 'Good', 'Excellent'],
        ['Fair', 'Fair', 'Good', 'Good', 'Excellent', 'Excellent'],
    )


def test_oof_predictions_are_aligned_and_every_block_is_held_out():
    rows = tile_rows()
    calls = []

    class HeldOutEstimator:
        def fit(self, X, y, sample_weight):
            self.train_blocks = set(X.block_id)
            self.train_locations = set(zip(X.latitude, X.longitude))
            return self

        def predict(self, X):
            assert self.train_blocks.isdisjoint(X.block_id)
            assert self.train_locations.isdisjoint(zip(X.latitude, X.longitude))
            calls.extend(X.quadkey.tolist())
            return X.latitude.to_numpy() * 10

    folds, oof, summary = evaluate_baselines(rows, model_factories={'knn': HeldOutEstimator})
    assert sorted(calls) == sorted(rows.quadkey)
    assert oof.quadkey.tolist() == rows.quadkey.tolist()
    np.testing.assert_array_equal(oof.knn_prediction_mbps, rows.latitude.to_numpy() * 10)
    assert oof.groupby('block_id').fold.nunique().eq(1).all()
    assert folds.test_rows.sum() == len(rows)
    assert folds.test_rows_scored.sum() == len(rows) - 1
    assert summary.area_n_areas.iloc[0] > 0
    for train, test in spatial_folds(rows):
        assert set(rows.iloc[train].block_id).isdisjoint(rows.iloc[test].block_id)


def test_duplicate_tiles_and_insufficient_blocks_are_rejected():
    rows = tile_rows()
    with pytest.raises(ValueError, match='pooled'):
        evaluate_baselines(pd.concat([rows, rows.iloc[:1]]))
    with pytest.raises(ValueError):
        evaluate_baselines(rows.assign(block_id=0))


def test_empty_fold_tile_metrics_do_not_remove_oof_predictions():
    rows = tile_rows().assign(tests=1)
    rows['latitude'] = 21 + np.arange(len(rows)) * 0.0001
    _, oof, summary = evaluate_baselines(rows, model_factories={'knn': lambda: KNNBaseline(2)})
    assert oof.knn_prediction_mbps.notna().all()
    assert summary.area_n_areas.iloc[0] > 0


def test_training_saves_selection_evidence_and_reloadable_model(tmp_path, monkeypatch):
    rows = tile_rows()
    monkeypatch.setattr(config, 'ARTIFACTS_MODELS', tmp_path / 'models')
    monkeypatch.setattr(config, 'ARTIFACTS_REPORTS', tmp_path / 'reports')
    monkeypatch.setattr(config, 'TILES_FILE', tmp_path / 'tiles.csv')
    # Fingerprints retain normal repo-relative paths; the test source is intentionally external.
    monkeypatch.setattr(config, 'ROOT', tmp_path)
    for name in ['OOKLA_RAW_FILE', 'OPENCELLID_RAW_FILE', 'OSM_TOWERS_RAW_FILE',
                 'TOWERS_FILE', 'CELLS_FILE', 'HANOI_BOUNDARY_FILE', 'CONTEXT_GRID_FILE']:
        monkeypatch.setattr(config, name, tmp_path / name)
    rows.to_csv(config.TILES_FILE, index=False)
    factories = {'knn': lambda: KNNBaseline(2),
                 'random_forest': lambda: RandomForestBaseline(n_estimators=5)}
    monkeypatch.setattr(training, 'BASELINES', factories)
    monkeypatch.setattr(training, 'evaluate_baselines',
                        lambda data: evaluate_baselines(data, model_factories=factories))
    model_dir, report_dir = training.train_baselines()
    from speedmap.artifacts import load_model
    bundle, metadata = load_model('regional', model_dir.name)
    assert bundle['kind'] == 'regional_baseline'
    assert bundle['model_name'] == pd.read_csv(report_dir / 'summary.csv').iloc[0]['model']
    assert metadata['provenance']['input_sha256']['tiles.csv']
    assert len(pd.read_csv(report_dir / 'out_of_fold.csv')) == len(rows)
    assert json.loads((report_dir / 'manifest.json').read_text())['selected_model'] == bundle['model_name']
    np.testing.assert_equal(len(bundle['model'].predict(rows)), len(rows))
