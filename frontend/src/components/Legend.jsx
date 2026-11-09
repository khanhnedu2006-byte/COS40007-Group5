export const TOWER_COLOR = "#56978b";

export const QUALITY = [
  { name: "Poor", range: "< 15", color: "#bd6b55" },
  { name: "Fair", range: "15–100", color: "#b78c35" },
  { name: "Good", range: "100–200", color: "#479b7a" },
  { name: "Excellent", range: "200+", color: "#17756d" },
];

export default function Legend({ level }) {
  return <div className="quality-scale" aria-label="Download speed quality levels in Mbps">
    {QUALITY.map((quality) => <div key={quality.name} className={level === quality.name ? "is-active" : ""}>
      <span className="quality-bar" style={{ backgroundColor: quality.color }} />
      <strong>{quality.name}</strong><span>{quality.range}</span>
    </div>)}
  </div>;
}
