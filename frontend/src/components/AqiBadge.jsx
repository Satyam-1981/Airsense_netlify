import { AQI_COLORS } from "../utils";

export default function AqiBadge({ value, category }) {
  const color = AQI_COLORS[category] || "#8d9e98";
  return (
    <div className="aqi-gauge" style={{ "--aqi-color": color }}>
      <div className="aqi-gauge-inner">
        <span>MODELLED AQI</span>
        <strong>{Number.isFinite(value) ? value : "—"}</strong>
        <em>{category || "Awaiting data"}</em>
      </div>
    </div>
  );
}
