import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  Plus,
  RefreshCw,
  Star,
  TrendingUp,
  TriangleAlert,
  X,
} from "lucide-react";
import PanelTitle from "../components/PanelTitle";
import TrendChart from "../components/TrendChart";
import { api } from "../api";
import { pollutantLabel, pollutantUnit, formatTime } from "../utils";

export default function Insights({ city, favourites, toggleFavourite }) {
  const [comparison, setComparison] = useState([]);
  const [history, setHistory] = useState(null);
  const [anomalies, setAnomalies] = useState(null);
  const [pollutant, setPollutant] = useState("pm25");
  const [sourceFilter, setSourceFilter] = useState("");
  const [stationFilter, setStationFilter] = useState("");
  const [cityInput, setCityInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setBusy(true);
    setError("");
    try {
      const [historyResult, anomalyResult, ...cityResults] = await Promise.all([
        api.history(city, 30),
        api.anomalies(city),
        ...favourites.map((item) =>
          api
            .city(item)
            .catch((err) => ({
              city: { name: item },
              prediction: null,
              message: err.message,
            })),
        ),
      ]);
      setHistory(historyResult);
      setAnomalies(anomalyResult);
      setComparison(cityResults);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    load();
  }, [city, favourites.join("|")]);

  const sources = [
    ...new Set(
      (history?.series || [])
        .filter((row) => row.pollutant === pollutant)
        .map((row) => row.source),
    ),
  ];
  useEffect(() => {
    if (sources.length && !sources.includes(sourceFilter))
      setSourceFilter(sources[0]);
  }, [sources.join("|"), sourceFilter]);
  const stationOptions = [
    ...new Map(
      (history?.series || [])
        .filter(
          (row) =>
            row.pollutant === pollutant &&
            (!sourceFilter || row.source === sourceFilter),
        )
        .map((row) => [
          `${row.source}:${row.station_id}`,
          {
            id: `${row.source}:${row.station_id}`,
            name: row.station,
            source: row.source,
            stationId: row.station_id,
          },
        ]),
    ).values(),
  ];
  useEffect(() => {
    if (
      stationOptions.length &&
      !stationOptions.some((item) => item.id === stationFilter)
    )
      setStationFilter(stationOptions[0].id);
  }, [stationOptions.map((item) => item.id).join("|"), stationFilter]);
  const trend = useMemo(
    () =>
      (history?.series || [])
        .filter(
          (row) =>
            row.pollutant === pollutant &&
            (!sourceFilter || row.source === sourceFilter) &&
            (!stationFilter ||
              `${row.source}:${row.station_id}` === stationFilter),
        )
        .map((row) => ({ label: row.date.slice(5), value: row.average })),
    [history, pollutant, sourceFilter, stationFilter],
  );

  function addCity(event) {
    event.preventDefault();
    if (cityInput.trim()) {
      toggleFavourite(cityInput.trim(), true);
      setCityInput("");
    }
  }

  return (
    <>
      <PanelTitle
        eyebrow="SEE THE BIGGER PICTURE"
        title="Patterns worth paying attention to."
        description="Compare the places you care about, explore stored observations and spot unusual changes in station readings."
        action={
          <button className="btn btn-quiet" onClick={load} disabled={busy}>
            <RefreshCw size={15} className={busy ? "spin" : ""} /> Refresh
          </button>
        }
      />
      <section className="panel favourite-panel">
        <div className="panel-heading">
          <div>
            <div className="eyebrow">YOUR PLACES</div>
            <h3>Favourite city comparison</h3>
            <p>
              Save up to five cities on this device. Comparison values are
              loaded from the same current-data provider.
            </p>
          </div>
          <Star size={20} />
        </div>
        <form className="inline-add-form" onSubmit={addCity}>
          <input
            value={cityInput}
            onChange={(event) => setCityInput(event.target.value)}
            placeholder="Add an Indian city"
            aria-label="Add favourite city"
          />
          <button
            className="btn btn-primary"
            type="submit"
            disabled={favourites.length >= 5}
          >
            <Plus size={15} /> Add city
          </button>
        </form>
        <div className="comparison-grid">
          {comparison.map((item) => (
            <article
              className="comparison-card"
              key={item.city?.name || item.city?.latitude}
            >
              <div className="comparison-head">
                <strong>{item.city?.name || "City"}</strong>
                <button
                  className="icon-action"
                  onClick={() => toggleFavourite(item.city?.name || "")}
                  aria-label="Remove favourite"
                >
                  <X size={15} />
                </button>
              </div>
              <div className="comparison-aqi">
                {item.prediction?.aqi ?? "—"}
                <small>{item.prediction?.category || "No estimate"}</small>
              </div>
              <div className="comparison-sub">
                PM2.5{" "}
                <b>
                  {Number.isFinite(item.pollutants?.pm25)
                    ? `${item.pollutants.pm25.toFixed(1)} µg/m³`
                    : "—"}
                </b>
              </div>
              <div className="comparison-sub">
                Updated <b>{formatTime(item.modelled_at)}</b>
              </div>
              {item.message && (
                <small className="muted-text">{item.message}</small>
              )}
            </article>
          ))}
        </div>
        {!favourites.length && (
          <div className="empty-state compact">
            <Star size={22} />
            <p>
              Add a city to compare its current air-quality estimate with other
              saved places.
            </p>
          </div>
        )}
      </section>

      <section className="panel history-panel">
        <div className="panel-heading">
          <div>
            <div className="eyebrow">OBSERVATION HISTORY</div>
            <h3>What has been recorded?</h3>
            <p>
              Daily averages for one selected station and data source, using
              readings AtmoIQ actually stored over the last 30 days.
            </p>
          </div>
          <TrendingUp size={20} />
        </div>
        <div className="history-controls">
          <div className="history-selects">
            <label className="field-label">
              Pollutant
              <select
                value={pollutant}
                onChange={(event) => setPollutant(event.target.value)}
              >
                {["pm25", "pm10", "no2", "so2", "co", "o3", "nh3"].map(
                  (key) => (
                    <option key={key} value={key}>
                      {pollutantLabel(key)}
                    </option>
                  ),
                )}
              </select>
            </label>
            <label className="field-label">
              Data source
              <select
                value={sourceFilter}
                onChange={(event) => setSourceFilter(event.target.value)}
              >
                {sources.map((source) => (
                  <option key={source} value={source}>
                    {source}
                  </option>
                ))}
              </select>
            </label>
            <label className="field-label">
              Station
              <select
                value={stationFilter}
                onChange={(event) => setStationFilter(event.target.value)}
              >
                {stationOptions.map((station) => (
                  <option key={station.id} value={station.id}>
                    {station.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="history-count">
            <b>{history?.observation_count ?? 0}</b>
            <span>stored station snapshots</span>
          </div>
        </div>
        <TrendChart
          data={trend}
          dataKey="value"
          label={`${pollutantLabel(pollutant)} · ${pollutantUnit(pollutant)}`}
          color="#4c9b83"
          height={230}
        />
        <p className="chart-footnote">
          {history?.note ||
            "History appears as stations are retrieved and observations are saved. A scheduler can collect station readings regularly."}
        </p>
      </section>

      <section className="panel anomaly-panel">
        <div className="panel-heading">
          <div>
            <div className="eyebrow">UNUSUAL CHANGES</div>
            <h3>Pollution spike detection</h3>
            <p>
              Statistical flags compare a station's latest reading with its own
              recent history.
            </p>
          </div>
          <TriangleAlert size={20} />
        </div>
        {anomalies?.anomalies?.length ? (
          <div className="anomaly-list">
            {anomalies.anomalies.map((item, index) => (
              <article
                className="anomaly-row"
                key={`${item.station_id}-${item.pollutant}-${index}`}
              >
                <div className="anomaly-symbol">
                  <Activity size={17} />
                </div>
                <div className="anomaly-copy">
                  <strong>
                    {item.station} · {pollutantLabel(item.pollutant)}
                  </strong>
                  <span>
                    {item.city} · {formatTime(item.observed_at)}
                  </span>
                </div>
                <div className="anomaly-reading">
                  <b>{item.latest_value.toFixed(1)}</b>
                  <small>{pollutantUnit(item.pollutant)}</small>
                </div>
                <div className="anomaly-increase">
                  +{item.increase.toFixed(1)}
                  <small>above baseline</small>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-state compact">
            <Activity size={22} />
            <p>
              No unusual spikes are confirmed by the currently stored history.
              At least 10 earlier readings per station and pollutant are needed
              before a flag can be produced.
            </p>
          </div>
        )}
        <p className="chart-footnote">
          {anomalies?.note ||
            "An anomaly is a statistical signal, not proof of an incident or its source."}
        </p>
      </section>
      {error && <div className="inline-warning">{error}</div>}
    </>
  );
}
