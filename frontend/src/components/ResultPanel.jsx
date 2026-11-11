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
  const dataMode = result.source === "data";
  const simulatedTowers = result.nearest_towers.every((tower) => tower.source === "simulated");
  if (result.area_download_mbps == null) return <article className="snapshot result-card"><h3>No recorded region available</h3><p>No measured tiles lie within {(result.area_radius_m / 1000).toFixed(1)} km of this point. Choose another region or use a trained model for grid-backed estimates.</p></article>;
  const radius = `${(result.area_radius_m / 1000).toFixed(1)} km`;
  const level = result.area_quality_level;
  return <>
    <article className="snapshot result-card">
      <div className="result-location"><Icon name="pin" size={16} /><strong>{selected?.name || "Selected location"}</strong><span className="result-type">{demo ? "SIMULATED" : dataMode ? "DATA ESTIMATE" : "ESTIMATE"}</span></div>
      <p className="coordinates">{result.latitude.toFixed(5)}° N <span>/</span> {result.longitude.toFixed(5)}° E</p>
      <div className="speed-label"><Icon name="down" size={14} />REGIONAL DOWNLOAD SPEED</div>
      <div className="download-value">{result.area_download_mbps.toFixed(1)}<span>Mbps</span></div>
      <div className={`quality-badge quality-${level.toLowerCase()}`}><span />{level} connection</div>
      <p className="quality-description">{descriptions[level]}</p>
      <p className="area-context">Typical speed within {radius} of this point.</p>
      <p className="area-support">{demo ? `Simulated across ${result.area_grid_points} grid points.` : `${result.area_ookla_tiles} measured tiles used for sampling.`}
        {!demo && result.area_grid_points > 0 && ` Sparse coverage: ${result.area_grid_points} grid points added.`}</p>
      <Legend level={level} />
    </article>
    <section className="nearest-section" aria-label="Three nearest towers">
      <div className="nearest-heading"><Icon name="tower" size={16} /><h3>Closest {simulatedTowers ? "demo towers" : "cell locations"}</h3><span>ON THE MAP</span></div>
      {result.nearest_towers.map((tower, index) => <div className="nearest-row" key={tower.tower_id}>
        <span className="tower-number">{String(index + 1).padStart(2, "0")}</span><span>{tower.source === "simulated" ? "Demo tower" : "Cell location"} <small>{tower.tower_id}</small></span><strong>{formatDistance(tower.distance_m)}</strong>
      </div>)}
    </section>
    <details className="model-details"><summary>Behind the estimate<Icon name="chevron" size={14} /></summary>
      <p>{demo ? "These speeds are simulated. Tower locations use the local dataset when available." : dataMode ? "Recorded tile speeds are pooled using test-weighted log means. These historical measurements are not live speed tests." : "Predictions across nearby tiles are pooled using test-weighted log means. More heavily measured tiles contribute more to the regional estimate."}</p>
      <dl>{result.data_support && <div><dt>Latest nearby quarter</dt><dd>{result.data_support.latest_quarter}</dd></div>}<div><dt>Model</dt><dd>{demo ? "Simulated" : dataMode ? "Recorded data" : result.model_name === "knn" ? "KNN" : "Random Forest"}</dd></div><div><dt>Radius</dt><dd>{radius}</dd></div><div><dt>Version</dt><dd>{result.model_version}</dd></div></dl>
    </details>
  </>;
}
