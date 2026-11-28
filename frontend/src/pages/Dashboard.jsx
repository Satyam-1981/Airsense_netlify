import { useMemo, useState } from "react";
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  CalendarClock,
  MapPin,
  RefreshCw,
  Search,
  Star,
  Wind,
} from "lucide-react";
import PanelTitle from "../components/PanelTitle";
import StatCard from "../components/StatCard";
import AqiBadge from "../components/AqiBadge";
import TrendChart from "../components/TrendChart";
import {
  formatTime,
  getHealthAdvice,
  pollutantLabel,
  pollutantUnit,
} from "../utils";

export default function Dashboard({
  city,
  data,
  loading,
  onSearch,
  favourites,
  toggleFavourite,
  forecast,
  onNavigate,
  error,
}) {
  const [query, setQuery] = useState(city);
  const prediction = data?.prediction;
  const pollutants = data?.pollutants || {};
  const pollutantsToShow = ["pm25", "pm10", "no2", "so2", "co", "o3", "nh3"];
  const isFavourite = favourites.some(
    (item) => item.toLowerCase() === city.toLowerCase(),
  );
  const chart = useMemo(() => {
    const now = Date.now();
    return (forecast?.hours || [])
      .filter((row) => {
        const time = new Date(row.time).getTime();
        return time >= now && time <= now + 24 * 60 * 60 * 1000;
      })
      .map((row) => ({
        label: new Date(row.time).toLocaleTimeString("en-IN", {
          hour: "numeric",
        }),
        aqi: row.aqi,
      }))
      .filter((row) => Number.isFinite(row.aqi));
  }, [forecast]);
  const advice = getHealthAdvice(prediction?.category);

  async function submit(event) {
    event.preventDefault();
    if (query.trim()) {
      try {
        await onSearch(query.trim());
      } catch {
        /* The shell displays the request error. */
      }
    }
  }

  return (
    <>
      <PanelTitle
        eyebrow="YOUR LOCAL AIR PICTURE"
        title="Good air starts with good information."
        description="Understand what's in the air, what may happen next, and what you can do about it."
        action={
          <button
            className="btn btn-quiet"
            onClick={() => onSearch(city)}
            disabled={loading}
          >
            <RefreshCw size={15} className={loading ? "spin" : ""} /> Refresh
          </button>
        }
      />
      <section className="hero-panel">
        <div className="hero-glow" />
        <div className="hero-topline">
          <span className="hero-tag">
            <span className="pulse-dot" /> CITY AIR SNAPSHOT
          </span>
          <span className="hero-date">
            <CalendarClock size={14} /> Modelled hour ·{" "}
            {formatTime(data?.modelled_at)}
          </span>
        </div>
        <div className="hero-main">
          <div className="hero-copy">
            <div className="hero-location">
              <MapPin size={16} />
              {data?.city?.name || city}
              {data?.city?.state ? `, ${data.city.state}` : ""}
            </div>
            <h2>
              Know your air.
              <br />
              <i>Choose your next move.</i>
            </h2>
            <form className="city-search" onSubmit={submit}>
              <Search size={17} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search an Indian city"
                aria-label="Search an Indian city"
              />
              <button type="submit" disabled={loading}>
                {loading ? "Loading" : "Explore"}
              </button>
            </form>
            <div className="hero-source">
              {data?.source ||
                "Waiting for the latest modelled air-quality data."}
            </div>
          </div>
          <div className="hero-aqi-wrap">
            <AqiBadge value={prediction?.aqi} category={prediction?.category} />
            <div className="aqi-trust">
              {prediction
                ? prediction.model_agreement
                : "Model prediction unavailable"}
            </div>
            <button
              className={`favourite-button ${isFavourite ? "saved" : ""}`}
              onClick={() => toggleFavourite(city)}
            >
              <Star size={15} fill={isFavourite ? "currentColor" : "none"} />
              {isFavourite ? "Saved city" : "Save this city"}
            </button>
          </div>
        </div>
        {error && <div className="inline-warning">{error}</div>}
      </section>

      <div className="section-row">
        <div>
          <div className="eyebrow">WHAT'S IN THE AIR</div>
          <h2 className="section-title">Pollutant levels</h2>
        </div>
        <span className="section-caption">
          Native 3-hour CAMS points ·{" "}
          {data?.data_status === "available"
            ? "Complete inputs"
            : "Incomplete inputs"}
        </span>
      </div>
      <div className="stats-grid pollutant-grid">
        {pollutantsToShow.map((key, index) => (
          <StatCard
            key={key}
            label={pollutantLabel(key)}
            value={
              Number.isFinite(pollutants[key])
                ? pollutants[key].toFixed(key === "co" ? 2 : 1)
                : "—"
            }
            unit={pollutantUnit(key)}
            icon={index === 0 || index === 1 ? Activity : Wind}
            accent={index < 2 ? "mint" : "sky"}
            detail={
              key === "nh3"
                ? "Not supplied by CAMS Global"
                : pollutants[key] == null
                  ? "No modelled value"
                  : ["co", "o3"].includes(key)
                    ? "Max 3-point approximation"
                    : "24h mean of native 3h points"
            }
          />
        ))}
      </div>

      <div className="dashboard-grid">
        <section className="panel chart-panel">
          <div className="panel-heading">
            <div>
              <div className="eyebrow">NEXT 24 HOURS</div>
              <h3>Air quality outlook</h3>
            </div>
            <button
              className="text-button"
              onClick={() => onNavigate("Forecast")}
            >
              Full forecast <ArrowUpRight size={15} />
            </button>
          </div>
          <TrendChart data={chart} height={220} />
          <div className="chart-footnote">
            Native 3-hour CAMS Global AQI proxy points
          </div>
        </section>
        <section className="panel recommendation-card">
          <div className="recommend-icon">
            <Activity size={19} />
          </div>
          <div className="eyebrow">A LITTLE GUIDANCE</div>
          <h3>
            {prediction
              ? `${prediction.category} air quality`
              : "Your air update is loading"}
          </h3>
          <p>{advice[0]}</p>
          <div className="recommend-action">{advice[1]}</div>
          <button
            className="btn btn-dark"
            onClick={() => onNavigate("Health & Alerts")}
          >
            Health & alerts <ArrowUpRight size={15} />
          </button>
        </section>
      </div>

      <div className="dashboard-bottom-grid">
        <section className="panel info-panel">
          <div className="panel-heading">
            <div>
              <div className="eyebrow">SMARTER OUTDOOR PLANS</div>
              <h3>Lowest forecast point</h3>
            </div>
            <CalendarClock size={19} />
          </div>
          {forecast?.lowest_forecast_point ? (
            <>
              <strong className="window-time">
                {new Date(
                  forecast.lowest_forecast_point.time,
                ).toLocaleTimeString("en-IN", {
                  hour: "numeric",
                  minute: "2-digit",
                })}
              </strong>
              <p>
                Lowest available native 3-hour AQI proxy point in the next 24
                hours:{" "}
                <b>
                  {forecast.lowest_forecast_point.aqi} (
                  {forecast.lowest_forecast_point.category})
                </b>
                .
              </p>
            </>
          ) : (
            <p>
              No valid native forecast point is currently available. Missing
              pollutant inputs are not imputed.
            </p>
          )}
          <button
            className="text-button"
            onClick={() => onNavigate("Forecast")}
          >
            See forecast <ArrowUpRight size={15} />
          </button>
        </section>
        <section className="panel info-panel source-panel">
          <div className="panel-heading">
            <div>
              <div className="eyebrow">DATA TRANSPARENCY</div>
              <h3>Know what this number means</h3>
            </div>
            <Activity size={19} />
          </div>
          <p>
            AtmoIQ uses modelled atmospheric concentrations and a trained
            ensemble. This is not an official CPCB station AQI reading.
          </p>
          <div className="source-row">
            <span>Modelled hour</span>
            <b>{formatTime(data?.modelled_at)}</b>
          </div>
          <div className="source-row">
            <span>Fetched by AtmoIQ</span>
            <b>{formatTime(data?.fetched_at)}</b>
          </div>
          <div className="source-row">
            <span>Prediction coverage</span>
            <b>{prediction?.input_completeness || "Not available"}</b>
          </div>
          <button className="text-button" onClick={() => onNavigate("ML Lab")}>
            Explore model details <ArrowUpRight size={15} />
          </button>
        </section>
      </div>
    </>
  );
}
