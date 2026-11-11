"""Application prediction extent, independent of the training-data boundary."""
import json
from functools import lru_cache

from matplotlib.path import Path

from speedmap import config

OUTSIDE_MESSAGE = "This point is outside central Hanoi's prediction area. Choose a location inside the outlined area."


def prediction_boundary():
    return json.loads(config.PREDICTION_BOUNDARY_FILE.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _prediction_paths():
    geometry = prediction_boundary()["features"][0]["geometry"]
    polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    return [[Path(ring) for ring in polygon] for polygon in polygons]


def supports_location(lat, lon):
    point = (lon, lat)
    return any(outer.contains_point(point) and not any(hole.contains_point(point) for hole in holes)
               for outer, *holes in _prediction_paths()) and config.inside_hanoi(lat, lon)
