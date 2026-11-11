"""Run: pytest tests/test_context.py   (Person 1) — synthetic rasters, no download needed."""
import json

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
from rasterio.transform import from_origin  # noqa: E402

from speedmap import config  # noqa: E402
from speedmap.data import context  # noqa: E402
from speedmap.features.context_features import ContextGrid, context_features  # noqa: E402


def _write(path, data, lon0, lat1, res, nodata=None):
    profile = dict(driver="GTiff", height=data.shape[0], width=data.shape[1], count=1, dtype=data.dtype,
                   crs="EPSG:4326", transform=from_origin(lon0, lat1, res, res), nodata=nodata)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data, 1)


@pytest.fixture
def raw_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(context, "RAW_DIR", tmp_path)
    # 1 người mỗi pixel 0.0005° -> 4 người mỗi ô lưới 0.001°
    _write(tmp_path / "worldpop_vnm_2020.tif", np.ones((2000, 2000), "float32"), 105.3, 21.5, 0.0005, nodata=-99999)
    # nửa trên là đất xây dựng (50), nửa dưới là ruộng (40)
    lc = np.full((1000, 1000), 40, "uint8")
    lc[:500] = 50
    _write(tmp_path / "worldcover_test.tif", lc, 105.3, 21.5, 0.001)
    _write(tmp_path / "dem_test.tif", np.full((300, 300), 12.0, "float32"), 105.0, 22.0, 1 / 300)
    roads = {"elements": [{"geometry": [{"lat": 21.0, "lon": 105.80}, {"lat": 21.0, "lon": 105.82}]}]}
    (tmp_path / "osm_roads.json").write_text(json.dumps(roads))
    pois = {"elements": [{"lat": 21.0285, "lon": 105.8542}, {"center": {"lat": 21.0286, "lon": 105.8543}}]}
    (tmp_path / "osm_pois.json").write_text(json.dumps(pois))
    return tmp_path


def test_layers_and_features(raw_dir, tmp_path):
    layers = context.build_context_grid()
    assert set(layers) >= {"population", "builtup", "cropland", "elevation_m", "slope_deg", "roads_km", "pois"}
    out = tmp_path / "grid.npz"
    context.save_context_grid(layers, out)
    grid = ContextGrid.load(out)
    f = context_features([21.0285, 20.8], [105.8542, 105.8], grid)
    assert list(f.columns) == config.CONTEXT_FEATURES
    assert f["population_500m"].iloc[0] == pytest.approx(4 * 11 * 11)   # cửa sổ ±5 ô (~500 m), 4 người/ô
    assert f["builtup_1km"].iloc[0] == pytest.approx(1.0) and f["cropland_1km"].iloc[1] == pytest.approx(1.0)
    assert f["elevation_m"].iloc[0] == pytest.approx(12.0) and f["slope_deg"].iloc[0] == pytest.approx(0.0, abs=1e-3)
    assert f["pois_1km"].iloc[0] == 2
    road = context_features([21.0], [105.81], grid)["roads_km_1km"].iloc[0]
    assert 1.5 < road < 2.3   # đoạn đường dài ~2.08 km, cửa sổ 1 km giữ phần lớn


def test_missing_grid_gives_nan():
    with pytest.warns(UserWarning):
        f = context_features([21.0285], [105.8542], None)
    assert f.isna().all().all()
