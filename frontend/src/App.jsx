import { useCallback, useEffect, useState } from "react";
import { Menu, RefreshCw, Wind } from "lucide-react";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import Stations from "./pages/Stations";
import Forecast from "./pages/Forecast";
import HealthAlerts from "./pages/HealthAlerts";
import Insights from "./pages/Insights";
import MlLab from "./pages/MlLab";
import Community from "./pages/Community";
import Exposure from "./pages/Exposure";
import IndiaMap from "./pages/IndiaMap";
import RouteFinder from "./pages/RouteFinder";
import { api } from "./api";
import { readFavourites } from "./utils";
import "./styles.css";

export default function App() {
  const [page, setPage] = useState("Dashboard");
  const [city, setCity] = useState("Kolkata");
  const [dashboard, setDashboard] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [favourites, setFavourites] = useState(readFavourites);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [mobileOpen, setMobileOpen] = useState(false);

  const loadCity = useCallback(async (name) => {
    setLoading(true);
    setError("");
    try {
      const result = await api.city(name);
      setDashboard(result);
      setCity(result.city?.name || name);
      return result;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const loadForecast = useCallback(async (name) => {
    try {
      setForecast(await api.forecast(name));
    } catch {
      /* Keep the last successful forecast visible with its original fetch timestamp. */
    }
  }, []);

  useEffect(() => {
    loadCity("Kolkata").catch(() => {});
  }, [loadCity]);
  useEffect(() => {
    if (city) loadForecast(city);
  }, [city, loadForecast]);
  useEffect(() => {
    const timer = window.setInterval(
      () => {
        if (city) {
          loadCity(city).catch(() => {});
          if (page === "Dashboard") loadForecast(city);
        }
      },
      5 * 60 * 1000,
    );
    return () => window.clearInterval(timer);
  }, [city, page, loadCity, loadForecast]);
  useEffect(() => {
    localStorage.setItem("atmoiq-favourites", JSON.stringify(favourites));
  }, [favourites]);

  function toggleFavourite(name, forceAdd = false) {
    const clean = String(name || "").trim();
    if (!clean) return;
    setFavourites((old) => {
      const exists = old.some(
        (item) => item.toLowerCase() === clean.toLowerCase(),
      );
      if (exists && !forceAdd)
        return old.filter((item) => item.toLowerCase() !== clean.toLowerCase());
      if (exists || old.length >= 5) return old;
      return [...old, clean];
    });
  }

  const location = dashboard?.city || null;
  const prediction = dashboard?.prediction || null;
  const pageContent = {
    Dashboard: (
      <Dashboard
        city={city}
        data={dashboard}
        loading={loading}
        onSearch={loadCity}
        favourites={favourites}
        toggleFavourite={toggleFavourite}
        forecast={forecast}
        onNavigate={setPage}
        error={error}
      />
    ),
    Stations: <Stations city={city} location={location} />,
    "India Map": <IndiaMap />,
    "Cleanest Route": <RouteFinder city={city} />,
    Forecast: <Forecast city={city} />,
    "Health & Alerts": <HealthAlerts city={city} prediction={prediction} />,
    Insights: (
      <Insights
        city={city}
        favourites={favourites}
        toggleFavourite={toggleFavourite}
      />
    ),
    "ML Lab": <MlLab currentPollutants={dashboard?.pollutants} />,
    "Community Reports": <Community city={city} location={location} />,
    "My Exposure": (
      <Exposure
        city={city}
        prediction={prediction}
        pollutants={dashboard?.pollutants}
      />
    ),
  };

  return (
    <div className="app-shell">
      <Sidebar
        page={page}
        setPage={setPage}
        mobileOpen={mobileOpen}
        closeMobile={() => setMobileOpen(false)}
      />
      <main className="main-area">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="mobile-menu-button"
              aria-label="Open navigation"
              onClick={() => setMobileOpen(true)}
            >
              <Menu size={20} />
            </button>
            <div className="mobile-brand">
              <Wind size={19} /> AtmoIQ
            </div>
            <div className="breadcrumb">
              Air quality <span>/</span> <b>{page}</b>
            </div>
          </div>
          <div className="topbar-right">
            <span className="data-pill">
              <i />{" "}
              {dashboard?.prediction
                ? "MODEL ESTIMATE READY"
                : "AIR QUALITY MONITOR"}
            </span>
            <button
              className="top-refresh"
              title="Refresh selected city"
              onClick={() => loadCity(city)}
              disabled={loading}
            >
              <RefreshCw size={16} className={loading ? "spin" : ""} />
            </button>
            <div className="user-mark">AS</div>
          </div>
        </header>
        <div className="page-content">
          {pageContent[page]}
          <footer className="app-footer">
            <span>
              AtmoIQ · An air-quality companion for everyday decisions
            </span>
            <span>
              Data may be modelled, delayed or incomplete. Not an official CPCB
              alert service.
            </span>
          </footer>
        </div>
      </main>
    </div>
  );
}
