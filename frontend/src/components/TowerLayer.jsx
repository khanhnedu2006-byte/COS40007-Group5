import { memo, useEffect, useMemo, useRef, useState } from "react";
import { CircleMarker, Tooltip, useMap, useMapEvents } from "react-leaflet";
import { TOWER_COLOR } from "./Legend.jsx";

const SINGLE_STYLE = { color: "#fff", weight: 1.5, fillColor: TOWER_COLOR, fillOpacity: 0.85 };
const CLUSTER_STYLE = { color: "#fff", weight: 2, fillColor: TOWER_COLOR, fillOpacity: 0.9 };

const TowerMarker = memo(function TowerMarker({ group, map }) {
  const events = useMemo(() => group.count > 1 ? {
    click: () => map.setView(group.position, Math.min(map.getZoom() + 2, 18), { animate: false }),
  } : {}, [group, map]);
  return <CircleMarker center={group.position}
    radius={group.count > 1 ? Math.min(11 + Math.log2(group.count) * 2, 22) : 4}
    bubblingMouseEvents={false} pathOptions={group.count > 1 ? CLUSTER_STYLE : SINGLE_STYLE}
    eventHandlers={events}>
    {group.count > 1 ? <Tooltip permanent direction="center" className="cluster-count">{group.count}</Tooltip>
      : <Tooltip direction="top"><strong>{group.tower.source === "simulated" ? "Demo tower" : "Estimated cell location"}</strong><br />{group.tower.tower_id}</Tooltip>}
  </CircleMarker>;
});

const TowerLayer = memo(function TowerLayer({ towers }) {
  const map = useMap();
  const frame = useRef(null);
  const [view, setView] = useState(() => ({ zoom: map.getZoom(), bounds: map.getBounds().pad(0.15) }));
  useMapEvents({
    moveend: () => {
      cancelAnimationFrame(frame.current);
      frame.current = requestAnimationFrame(() => setView({ zoom: map.getZoom(), bounds: map.getBounds().pad(0.15) }));
    },
  });
  useEffect(() => () => cancelAnimationFrame(frame.current), []);
  const zoom = view.zoom;
  const groups = useMemo(() => {
    const cells = new Map();
    const size = zoom < 13 ? 48 : 32;
    for (const tower of towers) {
      const pixel = map.project([tower.latitude, tower.longitude], zoom);
      const key = `${zoom}:${Math.floor(pixel.x / size)}:${Math.floor(pixel.y / size)}`;
      const group = cells.get(key) || { key, latitude: 0, longitude: 0, count: 0, tower };
      group.latitude += tower.latitude;
      group.longitude += tower.longitude;
      group.count += 1;
      cells.set(key, group);
    }
    return [...cells.values()].map((group) => ({ ...group, position: [group.latitude / group.count, group.longitude / group.count] }));
  }, [map, towers, zoom]);
  return groups.filter((group) => view.bounds.contains(group.position))
    .map((group) => <TowerMarker key={group.key} group={group} map={map} />);
});

export default TowerLayer;
