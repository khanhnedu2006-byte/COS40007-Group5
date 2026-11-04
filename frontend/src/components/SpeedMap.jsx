import { useCallback, useRef, useState } from "react";
import Icon from "./Icon.jsx";
import MapScene from "./MapScene.jsx";
import { HANOI_CENTER } from "../hanoi.js";

export default function SpeedMap({ towers, boundary, area, showTowers, showBoundary, onToggleTowers, onToggleBoundary, result, selected, navigation, loading, onMapClick, disabled, demo }) {
  const mapRef = useRef(null);
  const [layersOpen, setLayersOpen] = useState(false);
  const [coordinates, setCoordinates] = useState("");
  const [locationError, setLocationError] = useState("");
  const [locating, setLocating] = useState(false);
  const [tileError, setTileError] = useState(false);
  const [zoom, setZoom] = useState(12);
  const handleTileError = useCallback((failed) => setTileError(failed), []);

  function jumpToLocation(event) {
    event.preventDefault();
    const parts = coordinates.trim().split(/[,;\s]+/);
    const [lat, lon] = parts.map(Number);
    if (parts.length !== 2 || !Number.isFinite(lat) || !Number.isFinite(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) {
      setLocationError("Enter latitude, longitude. For example: 21.0285, 105.8542");
      return;
    }
    setLocationError("");
    onMapClick(lat, lon, "Coordinates", true);
  }

  function locate() {
    setLocationError("");
    if (!navigator.geolocation) { setLocationError("Your browser doesn't support location access. Enter coordinates instead."); return; }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(({ coords }) => {
      setLocating(false);
      onMapClick(coords.latitude, coords.longitude, "Your location", true);
    }, () => { setLocating(false); setLocationError("Couldn't access your location. Check location permissions or enter coordinates instead."); }, { timeout: 10000, maximumAge: 60000 });
  }

  return (
    <section className="map-area" aria-label="Interactive map of Hanoi">
      <MapScene towers={towers} boundary={boundary} area={area} showTowers={showTowers} showBoundary={showBoundary}
        result={result} selected={selected} navigation={navigation} onMapClick={onMapClick}
        disabled={disabled} mapRef={mapRef} onTileError={handleTileError} onZoomChange={setZoom} />

      <div className="map-top-tools">
        <form className="coordinate-search" onSubmit={jumpToLocation}>
          <Icon name="pin" size={18} />
          <input aria-label="Latitude and longitude" placeholder="Hanoi coordinates: 21.0285, 105.8542" value={coordinates}
            onChange={(event) => setCoordinates(event.target.value)} disabled={disabled} />
          <button type="submit" aria-label="Explore coordinates" disabled={disabled}><Icon name="arrow" size={18} /></button>
        </form>
        <div className="layer-tools">
          <button className={`map-button layers-button ${layersOpen ? "active" : ""}`} aria-label="Map layers" aria-expanded={layersOpen} onClick={() => setLayersOpen((value) => !value)}><Icon name="layers" size={18} /><span>Layers</span></button>
          {layersOpen && <div className="layers-popover"><span className="eyebrow">MAP LAYERS</span>
            <label><input type="checkbox" checked={showTowers} onChange={onToggleTowers} /><span>{demo ? "Demo towers" : "Cell locations"}</span><span className="layer-dot" /></label>
            <label><input type="checkbox" checked={showBoundary} onChange={onToggleBoundary} /><span>Hanoi boundary</span><span className="layer-dash" /></label>
          </div>}
        </div>
      </div>
      {(locationError || tileError) && <div className="map-notice" role="alert"><Icon name="info" size={17} /><span>{locationError || "Map tiles couldn't load. An internet connection is needed for the street map; location estimates still work."}</span><button className="icon-button" aria-label="Dismiss map message" onClick={() => { setLocationError(""); setTileError(false); }}><Icon name="close" size={16} /></button></div>}
      <div className="map-place-label" aria-hidden="true"><span className="map-location-line" /><span>HÀ NỘI</span><small>21°01′ N · 105°51′ E</small></div>
      <div className="map-key"><span className="eyebrow">A LITTLE MAP CONTEXT</span><div><span className="key-tower" />{demo ? "Simulated tower" : "Estimated cell location"}</div><div><span className="key-boundary" />Hanoi city boundary</div></div>
      <div className="map-hint" role="status"><span className={loading ? "hint-spinner" : "hint-dot"} />{disabled ? "Waiting for the local service" : loading ? "Exploring your location…" : selected ? "Explore another location inside Hanoi" : "Hanoi only. Click inside the city boundary."}</div>
      <div className="map-controls">
        <span className="compass" aria-hidden="true">N<span>↑</span></span>
        <div className="zoom-buttons"><button aria-label="Zoom in" disabled={zoom >= 18} onClick={() => mapRef.current?.zoomIn()}><Icon name="plus" /></button><button aria-label="Zoom out" disabled={zoom <= 10} onClick={() => mapRef.current?.zoomOut()}><Icon name="minus" /></button></div>
        <button className="map-button" aria-label="Return to central Hanoi" title="Return to central Hanoi" onClick={() => mapRef.current?.setView(HANOI_CENTER, 12)}><Icon name="globe" /></button>
        <button className={`map-button ${locating ? "locating" : ""}`} aria-label="Use my location" title="Use my location" onClick={locate} disabled={disabled || locating}><Icon name="target" /></button>
      </div>
    </section>
  );
}
