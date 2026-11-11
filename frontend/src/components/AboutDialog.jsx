import { useEffect, useRef } from "react";
import Icon from "./Icon.jsx";

export default function AboutDialog({ open, onClose }) {
  const dialog = useRef(null);
  useEffect(() => {
    if (open) dialog.current?.showModal();
    else dialog.current?.close();
  }, [open]);
  return <dialog className="about-dialog" ref={dialog} onCancel={onClose} onClose={onClose}
    onClick={(event) => { if (event.target === dialog.current) onClose(); }} aria-labelledby="about-title">
    <div className="dialog-content">
      <button className="icon-button dialog-close" aria-label="Close about this project" onClick={onClose}><Icon name="close" /></button>
      <span className="eyebrow">COS40007 · ARTIFICIAL INTELLIGENCE ENGINEERING</span>
      <h2 id="about-title">A little more signal.<br />A little less guesswork.</h2>
      <p>Hanoi Signal is a student project exploring how machine learning can estimate typical mobile internet performance across Hanoi.</p>
      <div className="how-step"><span>01</span><div><h3>Pick a place</h3><p>Click the map, try a neighbourhood, or enter coordinates. Predictions are available inside Hanoi's administrative boundary.</p></div></div>
      <div className="how-step"><span>02</span><div><h3>Understand the estimate</h3><p>The selected KNN or Random Forest baseline estimates typical download speed within 500 m of your chosen point. The model is selected using spatial cross-validation. Measurements combine mobile networks and operators.</p></div></div>
      <div className="how-step"><span>03</span><div><h3>Keep the context</h3><p>These are area estimates, not live speed tests. Actual speeds depend on your device, operator, buildings and network load. Tower locations from OpenCelliD are approximate.</p></div></div>
      <div className="dialog-note"><Icon name="info" /><p>Demo speeds are simulated; tower locations use local data when available. Model mode reports regional estimates; sparse regions use extra grid samples.</p></div>
      <p className="about-credits">Planned data: <a href="https://github.com/teamookla/ookla-open-data" target="_blank" rel="noreferrer">Ookla</a> (CC BY-NC-SA 4.0) · <a href="https://opencellid.org/" target="_blank" rel="noreferrer">OpenCelliD</a> (CC BY-SA 4.0). Boundary: <a href="https://www.geoboundaries.org/" target="_blank" rel="noreferrer">geoBoundaries</a> (CC BY 4.0). Map: © <a href="https://stadiamaps.com/attribution/" target="_blank" rel="noreferrer">Stadia Maps</a>, OpenMapTiles and OpenStreetMap contributors.</p>
    </div>
  </dialog>;
}
