import Icon from "./Icon.jsx";
import Legend from "./Legend.jsx";
import { formatDistance } from "./SelectedPoint.jsx";

const descriptions = {
  Poor: "A lighter connection for everyday essentials.",
  Fair: "Room for everyday browsing and video calls.",
  Good: "Well suited to streaming, working and sharing.",
  Excellent: "Plenty of headroom for demanding downloads.",
};

export default function ResultPanel({ result, error, loading, selected, onRetry }) {
  if (loading) return <div className="snapshot loading-panel" role="status">
    <span className="loading-orbit"><Icon name="signal" size={25} /></span>
    <h3>Finding the signal…</h3><p>Looking around {selected?.name === "Selected location" ? "your chosen point" : selected?.name}.</p>
    <div className="skeleton" /><div className="skeleton short" />
  </div>;
  if (error) return <div className="snapshot error-panel" role="alert">
    <Icon name="info" size={28} /><h3>Let's try another connection</h3><p>{error}</p>
    {onRetry && <button className="text-button" onClick={onRetry}><Icon name="refresh" size={15} />Try this point again</button>}
  </div>;
  if (!result) return <div className="snapshot empty-panel">
    <div className="empty-graphic" aria-hidden="true"><span className="orbit orbit-one" /><span className="orbit orbit-two" /><span className="empty-center"><Icon name="pin" size={26} /></span><span className="orbit-dot dot-one" /><span className="orbit-dot dot-two" /><span className="orbit-dot dot-three" /></div>
    <h3>Every place has a signal.</h3><p>Pick a neighbourhood above or click<br />a point on the map to discover yours.</p>
    <span className="empty-caption"><span className="small-cross">+</span> YOUR NEXT CONNECTION STARTS HERE</span>
  </div>;
  const demo = result.source === "demo";
  const simulatedTowers = result.nearest_towers.every((tower) => tower.source === "simulated");
  const maximum = Math.max(result.download_high, 1);
  const lowPosition = result.download_low / maximum * 100;
  const pointPosition = result.download_mbps / maximum * 100;
  return <>
    <article className="snapshot result-card">
      <div className="result-location"><Icon name="pin" size={16} /><strong>{selected?.name || "Selected location"}</strong><span className="result-type">{demo ? "SIMULATED" : "ESTIMATE"}</span></div>
      <p className="coordinates">{result.latitude.toFixed(5)}° N <span>/</span> {result.longitude.toFixed(5)}° E</p>
      <div className="speed-label"><Icon name="down" size={14} />DOWNLOAD SPEED</div>
      <div className="download-value">{result.download_mbps.toFixed(1)}<span>Mbps</span></div>
      <div className={`quality-badge quality-${result.quality_level.toLowerCase()}`}><span />{result.quality_level} connection</div>
      <p className="quality-description">{descriptions[result.quality_level]}</p>
      <div className="range-section">
        <div><span>{demo ? "Illustrative range" : `${Math.round(result.confidence_level * 100)}% prediction range`}</span><strong>{result.download_low.toFixed(0)}–{result.download_high.toFixed(0)} <small>Mbps</small></strong></div>
        <div className="range-track"><span className="range-fill" style={{ left: `${lowPosition}%`, width: `${100 - lowPosition}%` }} /><span className="range-point" style={{ left: `${Math.min(pointPosition, 98)}%` }} /></div>
        {demo && <p>Demo range only; coverage has not been measured.</p>}
      </div>
      <div className="secondary-metrics">
        <div><span><Icon name="up" size={15} />Upload</span><strong>{result.upload_mbps.toFixed(1)}<small>Mbps</small></strong></div>
        <div><span><Icon name="clock" size={15} />Latency</span><strong>{result.latency_ms.toFixed(0)}<small>ms</small></strong></div>
      </div>
      <Legend level={result.quality_level} />
    </article>
    <section className="nearest-section" aria-label="Three nearest towers">
      <div className="nearest-heading"><Icon name="tower" size={16} /><h3>Closest {simulatedTowers ? "demo towers" : "cell locations"}</h3><span>NEAR THIS POINT</span></div>
      {result.nearest_towers.map((tower, index) => <div className="nearest-row" key={tower.tower_id}>
        <span className="tower-number">{String(index + 1).padStart(2, "0")}</span><span>{tower.source === "simulated" ? "Demo tower" : tower.source === "osm" ? "OSM mast" : "Cell location"} <small>{tower.tower_id}{tower.source === "opencellid" ? " · OpenCelliD" : ""}</small></span><strong>{formatDistance(tower.distance_m)}</strong>
      </div>)}
    </section>
    <details className="model-details"><summary>Behind the estimate<Icon name="chevron" size={14} /></summary>
      <p>{demo ? "Demo speeds and ranges are interface fixtures. Tower distances come from the loaded locations." : "The hybrid model adjusts a theoretical speed using local tower and location features."}</p>
      <dl><div><dt>{demo ? "Simulated theory" : "Theoretical speed"}</dt><dd>{result.theory_mbps.toFixed(1)} Mbps</dd></div><div><dt>Local adjustment</dt><dd>{result.local_effect_mbps > 0 ? "+" : ""}{result.local_effect_mbps.toFixed(1)} Mbps</dd></div><div><dt>Version</dt><dd>{result.model_version}</dd></div></dl>
    </details>
  </>;
}
