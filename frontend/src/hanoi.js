// The API supplies the application prediction area, separate from the training boundary.
export const HANOI_CENTER = [21.0285, 105.8542];
export const HANOI_BOUNDS = [[20.90, 105.73], [21.11, 105.95]];
export const HANOI_ONLY_MESSAGE = "This point is outside central Hanoi's prediction area. Choose a location inside the outlined area.";

function insideRing(ring, lat, lon) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if ((yi > lat) !== (yj > lat) && lon < (xj - xi) * (lat - yi) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

export function createHanoiArea(geojson) {
  const polygons = geojson.features.flatMap(({ geometry }) => geometry.type === "MultiPolygon" ? geometry.coordinates : [geometry.coordinates]);
  const points = polygons.flat(2);
  const latitudes = points.map((point) => point[1]);
  const longitudes = points.map((point) => point[0]);
  return {
    bounds: [[Math.min(...latitudes), Math.min(...longitudes)], [Math.max(...latitudes), Math.max(...longitudes)]],
    // Invert the city polygon to mute neighbouring provinces without a CSS filter.
    mask: [
      [[19, 104], [23, 104], [23, 108], [19, 108]],
      ...polygons.flatMap((polygon) => polygon.map((ring) => ring.map(([lon, lat]) => [lat, lon]))),
    ],
    contains: (lat, lon) => Number.isFinite(lat) && Number.isFinite(lon)
      && polygons.some(([outer, ...holes]) => insideRing(outer, lat, lon) && !holes.some((hole) => insideRing(hole, lat, lon))),
  };
}
