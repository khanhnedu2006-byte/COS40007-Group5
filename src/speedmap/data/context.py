"""Context layers for Hanoi on one regular grid (~100 m).   Owner: Person 1

Input:  data/raw/context/ (downloaded by scripts/fetch_context_data.py)
Output: data/reference/hanoi_context_grid.npz, small enough for git and for the backend (numpy only)

Layers per grid cell: population (people), builtup / trees / cropland / water (share of area 0–1),
elevation_m, slope_deg, roads_km (major roads), pois (shops, restaurants, schools, offices: Overture places or OSM).
"""
import json
import warnings

import numpy as np

from speedmap import config

RAW_DIR = config.DATA_RAW / "context"
WORLDCOVER_CLASSES = {"trees": 10, "cropland": 40, "builtup": 50, "water": 80}


def grid_shape():
    b, res = config.HANOI_BBOX, config.CONTEXT_GRID_RES_DEG
    rows = int(round((b["lat_max"] - b["lat_min"]) / res))
    cols = int(round((b["lon_max"] - b["lon_min"]) / res))
    return rows, cols


def grid_transform():
    from rasterio.transform import from_origin

    b, res = config.HANOI_BBOX, config.CONTEXT_GRID_RES_DEG
    return from_origin(b["lon_min"], b["lat_max"], res, res)


def _reproject(source, src_transform, src_crs, resampling, src_nodata=None) -> np.ndarray:
    from rasterio.warp import reproject

    dst = np.full(grid_shape(), np.nan, dtype="float32")
    reproject(source=source, destination=dst, src_transform=src_transform, src_crs=src_crs,
              src_nodata=src_nodata, dst_transform=grid_transform(), dst_crs="EPSG:4326",
              dst_nodata=np.nan, resampling=resampling)
    return dst


def _combine(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    # Ghép các ô raster liền nhau: lấy giá trị đã có, chỗ trống lấy từ ô kia
    return np.where(np.isnan(a), b, a)


def _window(src):
    """Part of a raster that covers the Hanoi box (empty window if the tile does not overlap)."""
    from rasterio.windows import Window, from_bounds

    b = config.HANOI_BBOX
    win = from_bounds(b["lon_min"], b["lat_min"], b["lon_max"], b["lat_max"], src.transform)
    win = win.round_offsets().round_lengths()
    try:
        return win.intersection(Window(0, 0, src.width, src.height))
    except Exception:  # rasterio báo lỗi khi hai cửa sổ không giao nhau
        return Window(0, 0, 0, 0)


def population_layer() -> np.ndarray:
    import rasterio
    from rasterio.enums import Resampling

    with rasterio.open(RAW_DIR / "worldpop_vnm_2020.tif") as src:
        win = _window(src)
        data = src.read(1, window=win).astype("float32")
        nodata = src.nodata
        if nodata is not None:
            data[data == nodata] = np.nan
        data[data < 0] = np.nan
        out = _reproject(data, src.window_transform(win), src.crs, Resampling.sum, src_nodata=np.nan)
    return np.nan_to_num(out, nan=0.0)


def landcover_layers() -> dict:
    import rasterio
    from rasterio.enums import Resampling

    layers = {k: np.full(grid_shape(), np.nan, dtype="float32") for k in WORLDCOVER_CLASSES}
    for tile in sorted(RAW_DIR.glob("worldcover_*.tif")):
        with rasterio.open(tile) as src:
            win = _window(src)
            if win.width <= 0 or win.height <= 0:
                continue
            classes = src.read(1, window=win)
            transform = src.window_transform(win)
            for name, code in WORLDCOVER_CLASSES.items():
                # Tỉ lệ diện tích của lớp này trong mỗi ô lưới = trung bình của mặt nạ 0/1
                mask = (classes == code).astype("float32")
                layers[name] = _combine(layers[name], _reproject(mask, transform, src.crs, Resampling.average))
    return layers


def elevation_layers() -> dict:
    import rasterio
    from rasterio.enums import Resampling

    elev = np.full(grid_shape(), np.nan, dtype="float32")
    for tile in sorted(RAW_DIR.glob("dem_*.tif")):
        with rasterio.open(tile) as src:
            win = _window(src)
            if win.width <= 0 or win.height <= 0:
                continue
            data = src.read(1, window=win).astype("float32")
            elev = _combine(elev, _reproject(data, src.window_transform(win), src.crs, Resampling.average, src.nodata))
    res = config.CONTEXT_GRID_RES_DEG
    lat0 = (config.HANOI_BBOX["lat_min"] + config.HANOI_BBOX["lat_max"]) / 2
    dy, dx = res * 110_570, res * 111_320 * np.cos(np.radians(lat0))
    gy, gx = np.gradient(np.nan_to_num(elev, nan=float(np.nanmean(elev))), dy, dx)
    slope = np.degrees(np.arctan(np.hypot(gx, gy))).astype("float32")
    return {"elevation_m": elev, "slope_deg": slope}


def _cell_index(lat, lon):
    b, res = config.HANOI_BBOX, config.CONTEXT_GRID_RES_DEG
    rows, cols = grid_shape()
    r = np.floor((b["lat_max"] - np.asarray(lat)) / res).astype(int)
    c = np.floor((np.asarray(lon) - b["lon_min"]) / res).astype(int)
    ok = (r >= 0) & (r < rows) & (c >= 0) & (c < cols)
    return r, c, ok


def road_layer(path=None) -> np.ndarray:
    """Kilometres of major road in each grid cell (segments split into ~20 m pieces)."""
    path = path or RAW_DIR / "osm_roads.json"
    out = np.zeros(grid_shape(), dtype="float32")
    for el in json.loads(path.read_text(encoding="utf-8")).get("elements", []):
        pts = np.array([(g["lat"], g["lon"]) for g in el.get("geometry", [])])
        for (la1, lo1), (la2, lo2) in zip(pts[:-1], pts[1:]):
            km = np.hypot((la2 - la1) * 110.57, (lo2 - lo1) * 111.32 * np.cos(np.radians(la1)))
            n = max(int(km / 0.02), 1)
            t = (np.arange(n) + 0.5) / n
            r, c, ok = _cell_index(la1 + t * (la2 - la1), lo1 + t * (lo2 - lo1))
            np.add.at(out, (r[ok], c[ok]), km / n)
    return out


def poi_path():
    """Overture places if downloaded (scripts/fetch_places.py), otherwise OpenStreetMap POIs."""
    for name in ("overture_places.json", "osm_pois.json"):
        if (RAW_DIR / name).exists():
            return RAW_DIR / name
    return None


def poi_layer(path=None) -> np.ndarray:
    path = path or poi_path()
    lat, lon = [], []
    for el in json.loads(path.read_text(encoding="utf-8")).get("elements", []):
        la = el.get("lat", el.get("center", {}).get("lat"))
        lo = el.get("lon", el.get("center", {}).get("lon"))
        if la is not None and lo is not None:
            lat.append(la)
            lon.append(lo)
    out = np.zeros(grid_shape(), dtype="float32")
    r, c, ok = _cell_index(np.array(lat), np.array(lon))
    np.add.at(out, (r[ok], c[ok]), 1)
    return out


def build_context_grid() -> dict:
    """Build every layer whose raw file exists; missing sources are skipped with a warning."""
    layers = {}
    steps = [
        ("worldpop_vnm_2020.tif", lambda: {"population": population_layer()}),
        ("worldcover_*.tif", landcover_layers),
        ("dem_*.tif", elevation_layers),
        ("osm_roads.json", lambda: {"roads_km": road_layer()}),
        ("*_p*.json", lambda: {"pois": poi_layer()}),
    ]
    for pattern, step in steps:
        if not list(RAW_DIR.glob(pattern)):
            warnings.warn(f"{pattern} not found in {RAW_DIR}: layer skipped")
            continue
        layers.update(step())
        print(f"  layer(s) from {pattern}: done", flush=True)
    return layers


def save_context_grid(layers: dict, path=config.CONTEXT_GRID_FILE) -> None:
    b = config.HANOI_BBOX
    meta = np.array([b["lat_max"], b["lon_min"], config.CONTEXT_GRID_RES_DEG])
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, _meta=meta, **{k: v.astype("float32") for k, v in layers.items()})
