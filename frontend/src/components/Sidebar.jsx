import Icon from "./Icon.jsx";
import ResultPanel from "./ResultPanel.jsx";

export default function Sidebar({ towerCount, result, error, loading, selected, places, onSelect, disabled, simulatedTowers, onRetry }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-intro">
        <span className="eyebrow"><span className="tiny-line" /> A MORE CONNECTED HANOI</span>
        <h1>Good places.<br /><em>Better signal.</em></h1>
        <p>A little insight before you arrive. Explore mobile internet speeds, one place at a time.</p>
      </div>
      <section className="places-section" aria-labelledby="places-heading">
        <div className="section-heading"><h2 id="places-heading">Start somewhere familiar</h2><span>01 — EXPLORE</span></div>
        <div className="place-grid">
          {places.map((place) => <button key={place.name} className={`place-button ${selected?.name === place.name ? "selected" : ""}`} title={place.label} disabled={disabled}
            onClick={() => onSelect(place.lat, place.lon, place.name, true)}>
            <Icon name="pin" size={14} /><span>{place.name}</span><Icon name="arrow" size={13} />
          </button>)}
        </div>
      </section>
      <section className="result-section" aria-labelledby="result-heading" aria-busy={loading}>
        <div className="section-heading"><h2 id="result-heading">Your signal snapshot</h2><span>02 — DISCOVER</span></div>
        <div aria-live="polite" aria-atomic="true">
          <ResultPanel result={result} error={error} loading={loading} selected={selected} onRetry={onRetry} />
        </div>
      </section>
      <footer className="sidebar-footer">
        <div><span className="footer-icon"><Icon name="tower" size={16} /></span><span><strong>{towerCount.toLocaleString()} {simulatedTowers ? "demo towers" : "cell locations"}</strong><small>{simulatedTowers ? "Simulated locations for interface development" : "Local tower dataset · 4G + 5G"}</small></span></div>
        <p>A student-built view of Hanoi.<br />Made with curiosity, shared with context.</p>
        <span className="footer-course">SWINBURNE · COS40007</span>
      </footer>
    </aside>
  );
}
