"""Rebuild the central application boundary from the current tower distribution.

Run from the repository root: python scripts/build_prediction_area.py
This is a coverage heuristic, not an accuracy evaluation. Training inputs are unchanged.
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.path import Path as PolygonPath
from scipy.ndimage import (
    binary_closing,
    binary_fill_holes,
    binary_opening,
    gaussian_filter,
    label,
)
from sklearn.neighbors import BallTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from speedmap import config
from speedmap.data.boundary import contains
from speedmap.data.catalog import file_digest, load_tile_table, load_tower_table
from speedmap.features.spatial import EARTH_RADIUS_M

SUPPORT_RADIUS_M = 1500
MIN_TOWERS = 16
MAX_OBSERVATION_DISTANCE_M = 1000
CLOSE_RADIUS_M = 1000
OPEN_RADIUS_M = 1500
GRID_STEP_M = 250


def build_prediction_area():
    towers = load_tower_table()
    tiles = load_tile_table()
    tree = BallTree(np.radians(towers[["latitude", "longitude"]]), metric="haversine")
    # Search all Hanoi rather than clipping to an arbitrary central rectangle.
    boundary = json.loads(config.HANOI_BOUNDARY_FILE.read_text(encoding="utf-8"))
    geometry = boundary["features"][0]["geometry"]
    polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    coordinates = np.vstack([ring for polygon in polygons for ring in polygon])
    west, south = coordinates.min(axis=0)
    east, north = coordinates.max(axis=0)
    # A margin keeps morphology from truncating regions at the analysis edge.
    margin = 0.03
    latitudes = np.arange(south - margin, north + margin, GRID_STEP_M / 111_320)
    longitudes = np.arange(west - margin, east + margin,
                           GRID_STEP_M / (111_320 * np.cos(np.radians(config.HANOI_CENTER[0]))))
    lon, lat = np.meshgrid(longitudes, latitudes)
    query = np.radians(np.column_stack([lat.ravel(), lon.ravel()]))
    counts = tree.query_radius(query, r=SUPPORT_RADIUS_M / EARTH_RADIUS_M,
                              count_only=True).reshape(lat.shape)
    observations = BallTree(np.radians(tiles[["latitude", "longitude"]]), metric="haversine")
    distance = observations.query(query, k=1)[0].reshape(lat.shape) * EARTH_RADIUS_M
    inside = contains(lat.ravel(), lon.ravel()).reshape(lat.shape)
    supported = (counts >= MIN_TOWERS) & (distance <= MAX_OBSERVATION_DISTANCE_M) & inside

    def disk(radius_m):
        radius = int(radius_m // GRID_STEP_M)
        y, x = np.ogrid[-radius:radius + 1, -radius:radius + 1]
        return x * x + y * y <= radius * radius

    # Bridge small urban gaps, then remove narrow road-like extensions.
    supported = binary_closing(supported, structure=disk(CLOSE_RADIUS_M))
    supported = binary_opening(supported, structure=disk(OPEN_RADIUS_M))
    components, _ = label(supported)  # Keep the connected core around Hoan Kiem.
    centre = (np.abs(latitudes - config.HANOI_CENTER[0]).argmin(),
              np.abs(longitudes - config.HANOI_CENTER[1]).argmin())
    component = components[centre]
    if component == 0:
        raise ValueError("Central Hanoi does not meet the tower support rule; review the input dataset.")
    core = binary_fill_holes(components == component)
    core = (gaussian_filter(core.astype(float), sigma=1) >= 0.5) & inside
    core = binary_fill_holes(core)
    fig, ax = plt.subplots()
    contour = ax.contourf(lon, lat, core.astype(float), levels=[0.5, 1.5])
    polygons = []
    for path in contour.get_paths():
        rings = path.to_polygons()
        if rings:
            # Keep the exterior outline and fill all interior pockets.
            polygons.append([np.round(rings[0], 7).tolist()])
    plt.close(fig)
    if len(polygons) != 1:
        raise ValueError("Expected one connected central polygon; inspect the generated contour.")
    outline = PolygonPath(polygons[0][0])
    return {"type": "FeatureCollection", "features": [{
        "type": "Feature",
        "properties": {
            "name": "Central Hanoi supported prediction area",
            "description": "Smoothed connected urban area seeded by 16 towers within 1.5 km and an observation within 1 km; narrow corridors removed and interior holes filled. Coverage heuristic, not validated accuracy.",
            "interior_holes_filled": True,
            "tower_count": len(towers), "towers_sha256": file_digest(config.TOWERS_FILE),
            "included_tower_count": int(outline.contains_points(towers[["longitude", "latitude"]]).sum()),
            "included_tile_count": int(outline.contains_points(tiles[["longitude", "latitude"]]).sum()),
            "support_radius_m": SUPPORT_RADIUS_M, "minimum_towers": MIN_TOWERS,
            "grid_step_m": GRID_STEP_M,
            "tiles_sha256": file_digest(config.TILES_FILE),
            "max_observation_distance_m": MAX_OBSERVATION_DISTANCE_M,
            "closing_radius_m": CLOSE_RADIUS_M, "opening_radius_m": OPEN_RADIUS_M,
            "approximate_area_km2": round(float(core.sum()) * GRID_STEP_M ** 2 / 1e6, 1),
        },
        "geometry": {"type": "Polygon", "coordinates": polygons[0]},
    }]}


if __name__ == "__main__":
    boundary = build_prediction_area()
    config.PREDICTION_BOUNDARY_FILE.write_text(json.dumps(boundary, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {config.PREDICTION_BOUNDARY_FILE}")
