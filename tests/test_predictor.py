"""Exercise serialized baselines with the actual shared regional sampler/features."""
import json

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.schemas import PredictionResponse
from speedmap import artifacts, config
from speedmap.inference.predictor import Predictor
from speedmap.models.baselines import KNNBaseline, RandomForestBaseline


@pytest.fixture(params=['knn', 'random_forest'])
def saved_model(request, tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'ARTIFACTS_MODELS', tmp_path)
    towers = pd.DataFrame({
        'tower_id': [1, 2, 3], 'latitude': [21.0285, 21.03, 21.04],
        'longitude': [105.8542, 105.85, 105.86],
    })
    cells = pd.DataFrame({'latitude': [21.0285, 21.03], 'longitude': [105.8542, 105.85], 'operator': [1, 4]})
    tiles = pd.DataFrame({'quadkey': ['x'], 'latitude': [21.029], 'longitude': [105.855], 'devices': [40], 'tests': [12]})
    tower_file = tmp_path / 'hanoi_towers.csv'
    towers.to_csv(tower_file, index=False)
    monkeypatch.setattr(config, 'TOWERS_FILE', tower_file)
    monkeypatch.setattr('speedmap.inference.predictor.load_cells', lambda: cells)
    monkeypatch.setattr('speedmap.inference.predictor.load_tiles', lambda: tiles)
    # Physics remains unfinished; neither baseline requires it.
    def unexpected_physics(*args):
        raise AssertionError('Regional baseline serving must not call physics')

    monkeypatch.setattr('speedmap.features.tower_features.theoretical_speed_mbps', unexpected_physics)
    rows = pd.DataFrame({c: [1., 2., 3.] for c in config.FEATURE_COLUMNS})
    rows['latitude'] = [21.02, 21.03, 21.04]
    rows['longitude'] = [105.85, 105.86, 105.87]
    rows['theory_mbps'] = np.nan
    rows[config.CONTEXT_FEATURES] = np.nan
    model = KNNBaseline(2) if request.param == 'knn' else RandomForestBaseline(5, 1)
    model.fit(rows, np.full(3, 133.))
    bundle = {'kind': 'regional_baseline', 'model': model, 'model_name': request.param,
              'area_radius_m': config.AREA_RADIUS_M}
    return artifacts.save_model(bundle, 'regional', feature_columns=model.columns)


def test_baseline_serves_regional_response_without_physics(saved_model):
    predictor = Predictor(run_id=saved_model.name)
    result = PredictionResponse.model_validate(predictor.predict(21.0285, 105.8542))
    assert result.source == 'model'
    assert result.area_download_mbps == 133
    assert result.area_radius_m == 500
    assert result.area_quality_level == 'Good'
    assert result.area_ookla_tiles == 1
    assert result.area_grid_points > 0
    assert result.model_version == saved_model.name
    assert len(predictor.tower_list()) == 3
    with TestClient(create_app('model', predictor)) as client:
        status = client.get('/api/health').json()
        assert status['ready'] and status['model_loaded']
        payload = client.get('/api/predict?lat=21.0285&lon=105.8542').json()
        assert payload['area_download_mbps'] == 133
        assert payload['area_points'] == payload['area_ookla_tiles'] + payload['area_grid_points']


def test_incompatible_feature_contract_is_rejected(saved_model):
    metadata_file = saved_model / 'metadata.json'
    metadata = json.loads(metadata_file.read_text())
    metadata['feature_columns'] = ['different_feature']
    metadata_file.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match='feature columns'):
        Predictor()


def test_nonfinite_model_prediction_is_rejected_on_startup(saved_model, monkeypatch):
    for estimator in (KNNBaseline, RandomForestBaseline):
        monkeypatch.setattr(estimator, 'predict', lambda self, X: np.full(len(X), np.nan))
    with pytest.raises(ValueError, match='finite'):
        Predictor()


def test_legacy_point_bundle_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'ARTIFACTS_MODELS', tmp_path)
    artifacts.save_model({'model': object()}, 'regional')
    with pytest.raises(ValueError, match='regional_baseline'):
        Predictor()


def test_model_trained_on_different_towers_is_rejected(saved_model):
    config.TOWERS_FILE.write_text(config.TOWERS_FILE.read_text().replace('21.0285', '21.0295'))
    with pytest.raises(ValueError, match='towers data differs'):
        Predictor()


def test_unversioned_model_is_rejected(saved_model):
    path = saved_model / 'metadata.json'
    metadata = json.loads(path.read_text())
    metadata.pop('data_fingerprints')
    path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match='provenance'):
        Predictor()


def test_pinned_older_run_keeps_its_evaluated_radius(saved_model):
    import joblib

    path = saved_model / 'model.joblib'
    bundle = joblib.load(path)
    bundle['area_radius_m'] = 1500
    joblib.dump(bundle, path)
    assert Predictor().predict(21.0285, 105.8542)['area_radius_m'] == 1500
