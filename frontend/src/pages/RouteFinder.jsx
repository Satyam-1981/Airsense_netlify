import { useEffect, useState } from "react";
import { Route } from "lucide-react";
import PanelTitle from "../components/PanelTitle";
import MapView from "../components/MapView";
import { api } from "../api";

export default function RouteFinder({ city }) {
  const [start, setStart] = useState(city || "");
  const [end, setEnd] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (city) setStart(city);
  }, [city]);
  async function compare(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      setResult(await api.route(start, end));
    } catch (e) {
      setError(e.message);
      setResult(null);
    } finally {
      setBusy(false);
    }
  }
  const chosen = result?.chosen_route;
  const markers = chosen
    ? [
        {
          latitude: result.start.latitude,
          longitude: result.start.longitude,
          title: result.start.name,
          subtitle: "Route start",
        },
        {
          latitude: result.end.latitude,
          longitude: result.end.longitude,
          title: result.end.name,
          subtitle: "Destination",
        },
        ...(chosen.sampled_stations || []).map((s) => ({
          latitude: s.latitude,
          longitude: s.longitude,
          title: s.station,
          subtitle: `PM2.5 ${s.pm25} µg/m³ · measured ${new Date(s.observed_at).toLocaleString("en-IN")} · ${s.distance_km} km from route`,
        })),
      ]
    : [];
  return (
    <>
      <PanelTitle
        eyebrow="LOWER-EXPOSURE JOURNEY PLANNING"
        title="Cleanest route finder"
        description="Compare up to three available driving alternatives using nearby stored station readings. This is an indicative screening tool, not a turn-by-turn pollution sensor."
      />
      <section className="panel report-form-panel">
        <form className="stack-form" onSubmit={compare}>
          <div className="two-field-grid">
            <label className="field-label">
              Start city
              <input
                value={start}
                onChange={(e) => setStart(e.target.value)}
                required
              />
            </label>
            <label className="field-label">
              Destination city
              <input
                value={end}
                onChange={(e) => setEnd(e.target.value)}
                required
              />
            </label>
          </div>
          <button className="btn btn-primary" disabled={busy} type="submit">
            <Route size={15} /> {busy ? "Finding route…" : "Compare route"}
          </button>
        </form>
        {error && <div className="inline-warning">{error}</div>}
      </section>
      {result && (
        <>
          <section className="panel station-map-panel">
            <div className="panel-heading">
              <div>
                <div className="eyebrow">SUGGESTED DRIVING ROUTE</div>
                <h3>
                  {result.start.name} to {result.end.name}
                </h3>
                <p>
                  {chosen.distance_km} km · approximately{" "}
                  {chosen.duration_minutes} minutes · selected by{" "}
                  {result.selection_method}
                </p>
              </div>
              <Route size={20} />
            </div>
            <MapView
              center={[result.start.latitude, result.start.longitude]}
              markers={markers}
              routeCoordinates={chosen.geometry}
            />
          </section>
          <section className="panel station-list-panel">
            <div className="panel-heading">
              <div>
                <div className="eyebrow">NEARBY STATION SCREENING</div>
                <h3>PM2.5 context along the route</h3>
                <p>
                  Average of available unique stations within 20 km of sampled
                  route points.
                </p>
              </div>
            </div>
            <div className="comparison-aqi">
              {chosen.average_nearby_pm25 ?? "—"}
              <small>µg/m³ average PM2.5</small>
            </div>
            <p>{result.note}</p>
            <div className="comparison-grid">
              {(result.routes || []).map((route) => (
                <article className="comparison-card" key={route.route_number}>
                  <div className="eyebrow">
                    ROUTE OPTION {route.route_number}
                    {route.route_number === chosen.route_number
                      ? " · SELECTED"
                      : ""}
                  </div>
                  <div className="comparison-aqi">
                    {route.average_nearby_pm25 ?? "—"}
                    <small>PM2.5 µg/m³ nearby-station average</small>
                  </div>
                  <div className="comparison-sub">
                    {route.distance_km} km · {route.duration_minutes} min
                  </div>
                </article>
              ))}
            </div>
            {(chosen.sampled_stations || []).map((s) => (
              <p key={s.station}>
                {s.station} · {s.city} · PM2.5 {s.pm25} µg/m³ · PM2.5 time{" "}
                {new Date(s.observed_at).toLocaleString("en-IN")}
              </p>
            ))}
          </section>
        </>
      )}
      <div className="disclaimer">
        <strong>Route limitation</strong>
        <p>
          The routing provider may return up to three alternatives; AtmoIQ
          compares only those alternatives and uses nearby station readings as a
          coarse proxy. It does not measure pollution between stations or search
          every possible road. No PM2.5 comparison is shown when suitable recent
          readings are unavailable.
        </p>
      </div>
    </>
  );
}
