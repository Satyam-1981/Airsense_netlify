import {
  Wind,
  LayoutDashboard,
  RadioTower,
  CloudSun,
  HeartPulse,
  ChartNoAxesCombined,
  BrainCircuit,
  ShieldAlert,
  Footprints,
  ChevronLeft,
  MapPinned,
  Route,
} from "lucide-react";

const links = [
  ["Dashboard", LayoutDashboard],
  ["Stations", RadioTower],
  ["India Map", MapPinned],
  ["Cleanest Route", Route],
  ["Forecast", CloudSun],
  ["Health & Alerts", HeartPulse],
  ["Insights", ChartNoAxesCombined],
  ["ML Lab", BrainCircuit],
  ["Community Reports", ShieldAlert],
  ["My Exposure", Footprints],
];

export default function Sidebar({ page, setPage, mobileOpen, closeMobile }) {
  return (
    <>
      {mobileOpen && (
        <button
          className="mobile-scrim"
          aria-label="Close menu"
          onClick={closeMobile}
        />
      )}
      <aside className={`sidebar ${mobileOpen ? "sidebar-open" : ""}`}>
        <div className="brand-lockup">
          <div className="brand-icon">
            <Wind size={23} strokeWidth={2.3} />
          </div>
          <div>
            <strong>AtmoIQ</strong>
            <span>AIR QUALITY, MADE ACTIONABLE</span>
          </div>
          <button
            className="sidebar-close"
            onClick={closeMobile}
            aria-label="Close menu"
          >
            <ChevronLeft size={18} />
          </button>
        </div>
        <div className="sidebar-kicker">YOUR AIRSPACE</div>
        <nav className="sidebar-nav">
          {links.map(([label, Icon]) => (
            <button
              key={label}
              className={`nav-link ${page === label ? "active" : ""}`}
              onClick={() => {
                setPage(label);
                closeMobile();
              }}
            >
              <Icon size={18} strokeWidth={1.9} />
              <span>{label}</span>
              {page === label && <i />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <span className="pulse-dot" />
            <div>
              <b>Data-aware by design</b>
              <small>Sources and timestamps stay visible.</small>
            </div>
          </div>
          <div className="sidebar-footer">
            AtmoIQ · INDIA
            <br />A practical environmental companion
          </div>
        </div>
      </aside>
    </>
  );
}
