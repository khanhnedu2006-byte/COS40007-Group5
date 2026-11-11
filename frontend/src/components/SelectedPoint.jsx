import { memo } from "react";
import { CircleMarker, Polyline, Tooltip } from "react-leaflet";
import { QUALITY } from "./Legend.jsx";

export function formatDistance(metres) {
  return metres >= 1000 ? `${(metres / 1000).toFixed(2)} km` : `${Math.round(metres)} m`;
}

const SelectedPoint = memo(function SelectedPoint({ result, selected, showTowers }) {
  const point = [selected.lat, selected.lon];
  const color = QUALITY.find((quality) => quality.name === result?.quality_level)?.color || "#087f73";
  return <>
    {showTowers && result?.nearest_towers.map((tower, i) => <Polyline key={tower.tower_id}
      positions={[point, [tower.latitude, tower.longitude]]}
      pathOptions={{ color: "#087f73", weight: i === 0 ? 2 : 1.5, dashArray: "5 7", opacity: 0.7 }}>
      <Tooltip sticky>#{i + 1} · {formatDistance(tower.distance_m)}</Tooltip>
    </Polyline>)}
    {showTowers && result?.nearest_towers.map((tower, i) => <CircleMarker key={tower.tower_id}
      center={[tower.latitude, tower.longitude]} radius={7}
      pathOptions={{ color: "#fff", weight: 2, fillColor: "#087f73", fillOpacity: 1 }}>
      <Tooltip direction="top">Tower #{i + 1} · {formatDistance(tower.distance_m)}</Tooltip>
    </CircleMarker>)}
    <CircleMarker center={point} radius={19} interactive={false}
      pathOptions={{ color, weight: 1, fillColor: color, fillOpacity: 0.12 }} />
    <CircleMarker center={point} radius={9}
      pathOptions={{ color: "#fff", weight: 3, fillColor: color, fillOpacity: 1 }}>
      <Tooltip direction="top" offset={[0, -10]} permanent className="selected-tooltip">
        {result ? <div className="map-signal-reading" style={{ color }}><strong>{result.download_mbps.toFixed(1)} <small>Mbps</small></strong><span>{result.quality_level} connection · {result.source === "demo" ? "simulated" : result.source === "data" ? "data estimate" : "model estimate"}</span></div> : selected.name}
      </Tooltip>
    </CircleMarker>
  </>;
});

export default SelectedPoint;
