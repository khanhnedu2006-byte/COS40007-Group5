import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import SpeedMap from "./components/SpeedMap.jsx";
import Sidebar from "./components/Sidebar.jsx";
import Icon from "./components/Icon.jsx";
import AboutDialog from "./components/AboutDialog.jsx";
import { fetchBoundary, fetchHealth, fetchPrediction, fetchTowers } from "./api.js";
import { createHanoiArea, HANOI_ONLY_MESSAGE } from "./hanoi.js";

export const PLACES = [
  { name: "Hoàn Kiếm", label: "The old heart of Hanoi", lat: 21.0285, lon: 105.8542 },
  { name: "West Lake", label: "Lakeside neighbourhoods", lat: 21.0589, lon: 105.8233 },
  { name: "Cầu Giấy", label: "The city's western hub", lat: 21.0362, lon: 105.7906 },
  { name: "Hà Đông", label: "Explore the southwest", lat: 20.9719, lon: 105.7772 },
];

export default function App() {
  const [towers, setTowers] = useState([]);
  const [boundary, setBoundary] = useState(null);
  const [health, setHealth] = useState(null);
  const [showTowers, setShowTowers] = useState(false);
  const [showBoundary, setShowBoundary] = useState(true);
  const [result, setResult] = useState(null);
  const [selected, setSelected] = useState(null);
  const [navigation, setNavigation] = useState(null);
  const [error, setError] = useState("");
  const [connectionError, setConnectionError] = useState("");
  const [loading, setLoading] = useState(false);
  const [connecting, setConnecting] = useState(true);
  const [reload, setReload] = useState(0);
  const [aboutOpen, setAboutOpen] = useState(false);
  const predictionRequest = useRef(null);
  const requestNumber = useRef(0);
  const area = useMemo(() => boundary ? createHanoiArea(boundary) : null, [boundary]);
  const toggleTowers = useCallback(() => setShowTowers((value) => !value), []);
  const toggleBoundary = useCallback(() => setShowBoundary((value) => !value), []);

  const selectPoint = useCallback(async (lat, lon, name = "Selected location", move = false) => {
    predictionRequest.current?.abort();
    const controller = new AbortController();
    predictionRequest.current = controller;
    const request = ++requestNumber.current;
    setResult(null);
    setError("");
    if (!area?.contains(lat, lon)) {
      setSelected({ lat, lon, name, outside: true });
      setLoading(false);
      setError(HANOI_ONLY_MESSAGE);
      return;
    }
    setSelected({ lat, lon, name });
    setLoading(true);
    if (move) setNavigation({ lat, lon, id: request });
    try {
      const prediction = await fetchPrediction(lat, lon, controller.signal);
      if (request === requestNumber.current) setResult(prediction);
    } catch (err) {
      if (err.name !== "AbortError" && request === requestNumber.current) setError(err.message);
    } finally {
      if (request === requestNumber.current) setLoading(false);
    }
  }, [area]);

  useEffect(() => {
    const controller = new AbortController();
    async function connect() {
      setConnecting(true);
      setConnectionError("");
      setHealth(null);
      setTowers([]);
      setBoundary(null);
      const responses = await Promise.allSettled([
        fetchHealth(controller.signal), fetchTowers(controller.signal), fetchBoundary(controller.signal),
      ]);
      if (controller.signal.aborted) return;
      const [status, nodes, area] = responses;
      if (status.status === "fulfilled") setHealth(status.value);
      if (nodes.status === "fulfilled") setTowers(nodes.value);
      if (area.status === "fulfilled") setBoundary(area.value);
      const failed = responses.find((response) => response.status === "rejected");
      if (failed) setConnectionError(failed.reason.message);
      else if (!status.value.ready) setConnectionError("The prediction service isn't ready. Check the backend model setup, then retry.");
      setConnecting(false);
    }
    connect();
    return () => controller.abort();
  }, [reload]);

  useEffect(() => () => predictionRequest.current?.abort(), []);

  const retry = () => {
    predictionRequest.current?.abort();
    ++requestNumber.current;
    setLoading(false);
    setResult(null);
    setSelected(null);
    setError("");
    setReload((value) => value + 1);
  };
  const demo = health?.mode === "demo";
  const simulatedTowers = health?.tower_data_source === "simulated";

  return (
    <div className="app-shell">
      <a className="skip-link" href="#explorer">Skip to location explorer</a>
      <header className="app-header">
        <a href="./" className="brand" aria-label="Hanoi Signal home">
          <span className="brand-mark"><Icon name="signal" size={23} /></span>
          <span>hanoi<span className="brand-light">signal</span><span className="brand-dot">.</span></span>
        </a>
        <div className="header-center"><span className="active-nav">Signal explorer</span><span className="header-divider" /><span>Hanoi, Vietnam</span></div>
        <div className="header-actions">
          <span className={`service-badge ${health?.ready ? "connected" : ""}`}><span className="status-dot" />{connecting ? "Connecting" : health?.ready ? demo ? "Demo mode" : "Model connected" : "Service offline"}</span>
          <button className="about-button" aria-label="About this project" onClick={() => setAboutOpen(true)}><Icon name="info" size={17} /><span>About this project</span></button>
        </div>
      </header>
      <div className={`mode-banner ${connectionError ? "has-error" : ""}`} role="status">
        <Icon name={connectionError ? "info" : "globe"} size={15} />
        <span>{connectionError || (connecting ? "Connecting to your local signal explorer…" : demo ? simulatedTowers ? "You're exploring a demo. Speeds, ranges and tower locations are simulated while our model is in development." : "Demo mode uses your local tower dataset. Speeds and ranges are simulated while our model is in development." : "Area estimates for mobile internet, combining 4G and 5G. These are predictions, not live speed tests.")}</span>
        {connectionError && <button onClick={retry}><Icon name="refresh" size={14} />Reconnect</button>}
        {!connectionError && <span className="banner-project">COS40007 DESIGN PROJECT</span>}
      </div>
      <main className="layout" id="explorer">
        <Sidebar
          towerCount={towers.length} result={result} error={error} loading={loading}
          selected={selected} places={PLACES} onSelect={selectPoint}
          disabled={connecting || !health?.ready || !area} simulatedTowers={simulatedTowers}
          onRetry={selected && !selected.outside ? () => selectPoint(selected.lat, selected.lon, selected.name) : undefined}
        />
        <SpeedMap
          towers={towers} boundary={boundary} area={area} showTowers={showTowers} showBoundary={showBoundary}
          onToggleTowers={toggleTowers} onToggleBoundary={toggleBoundary}
          result={result} selected={selected} navigation={navigation} loading={loading}
          onMapClick={selectPoint} disabled={connecting || !health?.ready || !area} simulatedTowers={simulatedTowers}
        />
      </main>
      <AboutDialog open={aboutOpen} onClose={() => setAboutOpen(false)} />
    </div>
  );
}
