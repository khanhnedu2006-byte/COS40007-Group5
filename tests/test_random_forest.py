"""Focused tests for the non-physics Random Forest baseline."""
import numpy as np
import pandas as pd
import pytest

from ml.models import RandomForestBaseline as LegacyRandomForestBaseline
from speedmap import config
from speedmap.models.baselines import RandomForestBaseline


def _training_rows() -> pd.DataFrame:
    """Return a small complete feature table for model tests."""
    return pd.DataFrame(
        {
            "latitude": [21.00, 21.01, 21.02, 21.03],
            "longitude": [105.80, 105.81, 105.82, 105.83],
            "dist_nearest_tower_m": [100.0, 200.0, 300.0, 400.0],
            "towers_500m": [3, 2, 1, 0],
            "towers_1km": [6, 5, 4, 3],
            "theory_mbps": [np.nan, np.nan, np.nan, np.nan],
            "quarter_index": [8099, 8099, 8100, 8100],
        }
    )


def test_random_forest_excludes_theory_and_predicts() -> None:
    """An empty physics column cannot block the ordinary-ML baseline."""
    rows = _training_rows()
    model = RandomForestBaseline(n_estimators=5, min_samples_leaf=1).fit(
        rows,
        np.array([20.0, 40.0, 80.0, 160.0]),
        np.ones(4),
    )
    predictions = model.predict(rows)
    assert predictions.shape == (4,)
    assert "theory_mbps" not in model.columns
    assert model.columns == [
        column for column in config.FEATURE_COLUMNS if column != "theory_mbps"
    ]


def test_legacy_import_uses_canonical_implementation() -> None:
    """The old ml.models path does not maintain a separate forest."""
    assert issubclass(LegacyRandomForestBaseline, RandomForestBaseline)


def test_random_forest_rejects_missing_used_feature() -> None:
    """Missing non-physics inputs fail with a clear error before sklearn."""
    rows = _training_rows()
    rows.loc[0, "towers_1km"] = np.nan
    with pytest.raises(ValueError, match="finite and non-missing"):
        RandomForestBaseline(n_estimators=2).fit(rows, np.ones(4))
