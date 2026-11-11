import { formatDistance } from "./SelectedPoint.jsx";
import { useCallback, useRef, useState } from "react";
import Icon from "./Icon.jsx";
import MapScene from "./MapScene.jsx";
import { HANOI_CENTER } from "../hanoi.js";
import { BASEMAPS } from "../basemaps.js";
import { QUALITY } from "./Legend.jsx";

export default function SpeedMap({ towers, boundary, area, showTowers, showBoundary, onToggleTowers, onToggleBoundary, result, selected, navigation, loading, onMapClick, disabled, simulatedTowers }) {
  const mapRef = useRef(null);
  const [layersOpen, setLayersOpen] = useState(false);
  const [mapStyle, setMapStyle] = useState("signal");
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
        mapStyle={mapStyle} result={result} selected={selected} navigation={navigation} onMapClick={onMapClick}
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
            <fieldset className="basemap-options"><legend>Map style</legend>
              {Object.entries(BASEMAPS).map(([value, style]) => <label key={value}>
                <input type="radio" name="map-style" value={value} checked={mapStyle === value}
                  onChange={() => { setTileError(false); setMapStyle(value); }} />
                <span>{style.label}</span>
              </label>)}
            </fieldset>
            <label><input type="checkbox" aria-label="Tower locations" checked={showTowers} onChange={onToggleTowers} /><span>{simulatedTowers ? "Demo towers" : "Cell locations"}</span><span className="layer-dot" /></label>
            <label><input type="checkbox" checked={showBoundary} onChange={onToggleBoundary} /><span>Hanoi boundary</span><span className="layer-dash" /></label>
          </div>}
        </div>
      </div>
      {(locationError || tileError) && <div className="map-notice" role="alert"><Icon name="info" size={17} /><span>{locationError || "Map tiles couldn't load. Check your connection or try Detailed streets under Layers. Location estimates still work."}</span><button className="icon-button" aria-label="Dismiss map message" onClick={() => { setLocationError(""); setTileError(false); }}><Icon name="close" size={16} /></button></div>}
      <div className="map-key" aria-label="Download speed quality legend"><span className="eyebrow">DOWNLOAD QUALITY · MBPS</span>
        <div className="map-quality-key">{QUALITY.map((quality) => <div key={quality.name}>
          <span className="map-quality-label"><i style={{ backgroundColor: quality.color }} />{quality.name}</span><small>{quality.range}</small>
        </div>)}</div>
        {showBoundary && <div className="map-context-key"><span className="key-boundary" />Hanoi city boundary</div>}
        {result && <div className="map-context-key"><span className="key-boundary" />{formatDistance(result.area_radius_m ?? 500)} prediction radius</div>}
        {showTowers && <div className="map-context-key"><span className="key-tower" />{simulatedTowers ? "Simulated towers" : "Dataset cell locations"}</div>}
      </div>
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
