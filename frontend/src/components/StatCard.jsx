export default function StatCard({
  label,
  value,
  unit,
  icon: Icon,
  accent = "mint",
  detail,
}) {
  return (
    <div className="stat-card">
      <div className={`stat-icon ${accent}`}>{Icon && <Icon size={18} />}</div>
      <div className="stat-copy">
        <span>{label}</span>
        <strong>
          {value ?? "—"}
          <small>{unit}</small>
        </strong>
        {detail && <em>{detail}</em>}
      </div>
    </div>
  );
}
