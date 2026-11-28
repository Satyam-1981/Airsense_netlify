import { useEffect, useMemo, useState } from "react";
import {
  ArrowUpRight,
  CalendarClock,
  CloudSun,
  RefreshCw,
  Sunrise,
  Wind,
  FileDown,
} from "lucide-react";
import PanelTitle from "../components/PanelTitle";
import TrendChart from "../components/TrendChart";
import { api } from "../api";
import { formatTime, pollutantLabel, pollutantUnit } from "../utils";

export default function Forecast({ city }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [metric, setMetric] = useState("aqi");

  async function load() {
    setBusy(true);
    setError("");
    try {
      setData(await api.forecast(city));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    load();
    const timer = window.setInterval(load, 5 * 60 * 1000);
    return () => window.clearInterval(timer);
  }, [city]);

  const chartData = useMemo(
    () =>
      (data?.hours || [])
        .map((row) => ({
          label: new Date(row.time).toLocaleString("en-IN", {
            day: "numeric",
            month: "short",
            hour: "numeric",
          }),
          aqi: row.aqi,
          pm25: row.pollutants?.pm25,
          pm10: row.pollutants?.pm10,
        }))
        .filter((row) => Number.isFinite(row[metric])),
    [data, metric],
  );
  const lowestPoint = data?.lowest_forecast_point;

  return (
    <>
      <PanelTitle
        eyebrow="PLAN AHEAD, NOT JUST CHECK NOW"
        title="Your air, a little further ahead."
        description={`Native 3-hour CAMS Global forecast points for ${city}, with transparent limits on the requested prediction horizons.`}
        action={
          <div className="heading-actions">
            <a
              className="btn btn-quiet"
              href={`/api/reports/pdf/?city=${encodeURIComponent(city)}`}
            >
              <FileDown size={15} /> PDF report
            </a>
            <button className="btn btn-quiet" onClick={load} disabled={busy}>
              <RefreshCw size={15} className={busy ? "spin" : ""} /> Refresh
            </button>
          </div>
        }
      />
      {error && <div className="inline-warning">{error}</div>}
      <section className="panel forecast-table-panel">
        <div className="panel-heading">
          <div>
            <div className="eyebrow">SHORT-TERM ML FORECAST</div>
            <h3>Predicted AQI at key horizons</h3>
            <p>
              Nearest available provider forecast timestamp to each requested
              horizon.
            </p>
          </div>
          <CloudSun size={20} />
        </div>
        <div className="comparison-grid">
          {(
            data?.horizon_predictions ||
            [1, 3, 6, 24].map((h) => ({ hours_ahead: h }))
          ).map((item) => (
            <article className="comparison-card" key={item.hours_ahead}>
              <div className="eyebrow">
                {item.hours_ahead} HOUR{item.hours_ahead === 1 ? "" : "S"} AHEAD
              </div>
              <div className="comparison-aqi">
                {item.aqi ?? "—"}
                <small>{item.category || "No prediction"}</small>
              </div>
              <div className="comparison-sub">
                {item.time ? (
                  <>
                    Forecast point <b>{formatTime(item.time)}</b>
                    {item.actual_hours_ahead != null ? (
                      <small>
                        Actual lead: {item.actual_hours_ahead} hours
                      </small>
                    ) : null}
                  </>
                ) : (
                  <small>
                    {item.reason || "No native forecast point available"}
                  </small>
                )}
              </div>
            </article>
          ))}
        </div>
        <p className="chart-footnote">
          {data?.note ||
            "Predictions depend on available modelled forecast inputs and trained ML artifacts."}
        </p>
      </section>
      <section className="best-window-panel">
        <div className="best-window-icon">
          <Sunrise size={24} />
        </div>
        <div className="best-window-copy">
          <span className="eyebrow">LOWEST AVAILABLE FORECAST POINT</span>
          <h2>
            {lowestPoint
              ? formatTime(lowestPoint.time)
              : "No valid point in the next 24 hours"}
          </h2>
          <p>
            {lowestPoint
              ? `Lowest available native 3-hour AQI proxy point in the next 24 hours · ${lowestPoint.aqi} (${lowestPoint.category}).`
              : "A point is shown only when all six supported pollutant inputs are available and the trained model can produce an estimate."}
          </p>
        </div>
        <div className="best-window-tag">
          <Wind size={16} /> 3-hour point
        </div>
      </section>
      <section className="panel forecast-chart-panel">
        <div className="panel-heading">
          <div>
            <div className="eyebrow">PROVIDER FORECAST OUTPUT</div>
            <h3>Pollution trend</h3>
            <p>
              Native 3-hour CAMS Global points and ensemble AQI proxy estimates.
              No hourly interpolation is used.
            </p>
          </div>
          <CloudSun size={20} />
        </div>
        <div className="chart-tabs">
          {[
            ["aqi", "AQI proxy"],
            ["pm25", "PM2.5"],
            ["pm10", "PM10"],
          ].map(([key, label]) => (
            <button
              key={key}
              className={metric === key ? "selected" : ""}
              onClick={() => setMetric(key)}
            >
              {label}
            </button>
          ))}
        </div>
        <TrendChart
          data={chartData}
          height={290}
          dataKey={metric}
          color={metric === "aqi" ? "#148876" : "#d28c4f"}
          label={
            metric === "aqi"
              ? "AQI proxy"
              : `${pollutantLabel(metric)} · ${pollutantUnit(metric)}`
          }
        />
        <div className="chart-footnote">
          {chartData.length} native 3-hour points with valid{" "}
          {metric === "aqi" ? "ensemble estimates" : "pollutant values"} ·
          fetched by AtmoIQ {formatTime(data?.fetched_at)}
        </div>
      </section>
      <section className="panel forecast-table-panel">
        <div className="panel-heading">
          <div>
            <div className="eyebrow">DETAIL VIEW</div>
            <h3>Native 3-hour forecast points</h3>
            <p>
              Unavailable concentrations are left blank instead of being filled
              with zero or interpolated.
            </p>
          </div>
          <CalendarClock size={19} />
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Time (IST)</th>
                <th>AQI proxy</th>
                <th>PM2.5</th>
                <th>PM10</th>
                <th>NO₂</th>
                <th>SO₂</th>
                <th>CO</th>
                <th>O₃</th>
              </tr>
            </thead>
            <tbody>
              {(data?.hours || []).map((row) => (
                <tr key={row.time}>
                  <td>{formatTime(row.time)}</td>
                  <td>{row.aqi ?? "—"}</td>
                  {["pm25", "pm10", "no2", "so2", "co", "o3"].map((key) => (
                    <td key={key}>
                      {Number.isFinite(row.pollutants?.[key])
                        ? row.pollutants[key].toFixed(1)
                        : "—"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <div className="disclaimer">
        <strong>Forecast and activity guidance</strong>
        <p>
          {data?.note ||
            "Forecast concentrations are modelled atmospheric estimates, not guaranteed outcomes."}{" "}
          Outdoor-time guidance does not account for personal health, traffic
          microenvironments or indoor air quality. Follow official advisories.
        </p>
      </div>
    </>
  );
}
