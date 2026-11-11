import { memo, useEffect, useMemo, useRef } from "react";
import { Circle, GeoJSON, MapContainer, Polygon, ScaleControl, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";
import { HANOI_BOUNDS, HANOI_CENTER } from "../hanoi.js";
import { BASEMAPS } from "../basemaps.js";
import ClickHandler from "./ClickHandler.jsx";
import TowerLayer from "./TowerLayer.jsx";
import SelectedPoint, { formatDistance } from "./SelectedPoint.jsx";

const BOUNDARY_STYLE = { color: "#468b7b", weight: 2, dashArray: "6 6", fill: false };
const MASK_STYLE = { stroke: false, fillColor: "#edf0e9", fillOpacity: 0.76, fillRule: "evenodd" };

function MapActions({ navigation, mapRef, area, onZoomChange }) {
  const map = useMap();
  useMapEvents({ zoomend: () => onZoomChange(map.getZoom()) });
  useEffect(() => {
    mapRef.current = map;
    const container = map.getContainer();
    let width = container.clientWidth;
    let height = container.clientHeight;
    let frame;
    const observer = new ResizeObserver(([entry]) => {
      const nextWidth = Math.round(entry.contentRect.width);
      const nextHeight = Math.round(entry.contentRect.height);
      if (width === nextWidth && height === nextHeight) return;
      width = nextWidth;
      height = nextHeight;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => map.invalidateSize({ pan: false, debounceMoveend: true }));
    });
    observer.observe(container);
    return () => { observer.disconnect(); cancelAnimationFrame(frame); mapRef.current = null; };
  }, [map, mapRef]);
  useEffect(() => {
    map.setMaxBounds(area?.bounds || HANOI_BOUNDS);
  }, [map, area]);
  useEffect(() => {
    if (navigation && area?.contains(navigation.lat, navigation.lon)) {
      map.stop();
      map.setView([navigation.lat, navigation.lon], 14, { animate: false });
    }
  }, [map, navigation, area]);
  return null;
}

// Form keystrokes and popovers must never update Leaflet's layers.
const MapScene = memo(function MapScene({ towers, boundary, area, showTowers, showBoundary, mapStyle, result, selected, navigation, onMapClick, disabled, mapRef, onTileError, onZoomChange }) {
  const tileFailures = useRef(0);
  const tileEvents = useMemo(() => ({
    tileerror: () => { if (++tileFailures.current >= 3) onTileError(true); },
    tileload: () => { tileFailures.current = 0; onTileError(false); },
  }), [onTileError]);
  return <MapContainer center={HANOI_CENTER} zoom={12} minZoom={10} maxZoom={18}
    maxBounds={HANOI_BOUNDS} maxBoundsViscosity={1} inertia={false}
    zoomAnimation={false} fadeAnimation={false} markerZoomAnimation={false}
    wheelDebounceTime={100} preferCanvas zoomControl={false} className="map">
    <TileLayer key={mapStyle} url={BASEMAPS[mapStyle].url}
      attribution={BASEMAPS[mapStyle].attribution}
      bounds={HANOI_BOUNDS} noWrap updateWhenIdle updateWhenZooming={false} keepBuffer={1}
      eventHandlers={tileEvents} />
    <MapActions navigation={navigation} mapRef={mapRef} area={area} onZoomChange={onZoomChange} />
    <ClickHandler onMapClick={onMapClick} disabled={disabled} />
    {area && <Polygon positions={area.mask} interactive={false} pathOptions={MASK_STYLE} />}
    {showBoundary && boundary && <GeoJSON data={boundary} interactive={false} style={BOUNDARY_STYLE} />}
    {showTowers && <TowerLayer towers={towers} />}
    {result && selected && !selected.outside && <Circle
      center={[result.latitude, result.longitude]} radius={result.area_radius_m ?? 500}
      pathOptions={{ color: "#167665", weight: 2, dashArray: "7 5", fillColor: "#167665", fillOpacity: 0.09 }}
      bubblingMouseEvents={false}>
      <Tooltip sticky>{formatDistance(result.area_radius_m ?? 500)} radius around this point</Tooltip>
    </Circle>}
    {selected && !selected.outside && <SelectedPoint result={result} selected={selected} showTowers={showTowers} />}
    <ScaleControl position="bottomleft" imperial={false} />
  </MapContainer>;
});

export default MapScene;
