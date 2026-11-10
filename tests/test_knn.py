"""Focused tests for the geographic KNN baseline."""
import numpy as np
import pandas as pd
import pytest

from speedmap.models.baselines import KNNBaseline


def test_repeated_coordinates_are_combined_by_test_count() -> None:
    """Repeated quarters at one location occupy one neighbour position."""
    rows = pd.DataFrame(
        {"latitude": [21.0, 21.0, 21.0], "longitude": [105.0, 105.0, 106.0]}
    )
    model = KNNBaseline(n_neighbors=2).fit(
        rows,
        np.array([10.0, 30.0, 100.0]),
        np.array([1.0, 3.0, 1.0]),
    )
    query = pd.DataFrame({"latitude": [21.0], "longitude": [105.5]})
    assert model.predict(query)[0] == pytest.approx(62.5)


def test_invalid_aggregation_weight_is_rejected() -> None:
    """Zero or negative test counts cannot silently alter an average."""
    rows = pd.DataFrame({"latitude": [21.0], "longitude": [105.0]})
    with pytest.raises(ValueError, match="positive"):
        KNNBaseline(1).fit(rows, np.array([10.0]), np.array([0.0]))
