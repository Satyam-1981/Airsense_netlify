import { useEffect, useState } from "react";
import { MapPinned, RefreshCw, TriangleAlert } from "lucide-react";
import PanelTitle from "../components/PanelTitle";
import MapView from "../components/MapView";
import { api } from "../api";
import { formatTime } from "../utils";

export default function IndiaMap() {
  const [network, setNetwork] = useState(null);
  const [hotspots, setHotspots] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function load() {
    setBusy(true);
    setError("");
    try {
      const [networkResult, hotspotResult] = await Promise.allSettled([
        api.indiaNetwork(),
        api.detectedHotspots(),
      ]);
      if (networkResult.status === "fulfilled") setNetwork(networkResult.value);
      else throw networkResult.reason;
      if (hotspotResult.status === "fulfilled")
        setHotspots(hotspotResult.value.hotspots || []);
      else
        setError(
          `Station map loaded, but hotspot screening failed: ${hotspotResult.reason.message}`,
        );
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    load();
    const timer = window.setInterval(load, 60_000);
    return () => window.clearInterval(timer);
  }, []);
  const stationMarkers = (network?.stations || []).map((s) => ({
    latitude: s.latitude,
    longitude: s.longitude,
    title: `${s.name} · ${s.city}`,
    subtitle: `${s.source} · latest station update ${formatTime(s.observed_at)} · directory seen ${formatTime(s.directory_seen_at)} · ${
      Object.entries(s.pollutants || {})
        .map(
          ([k, v]) =>
            `${k.toUpperCase()} ${v} at ${formatTime(s.pollutant_times?.[k] || s.observed_at)}`,
        )
        .join(" · ") || "No pollutant values"
    }`,
  }));
  const hotspotMarkers = hotspots.map((h) => {
    const times = [
      h.reason?.includes("PM2.5")
        ? `PM2.5 ${formatTime(h.pollutant_times?.pm25 || h.observed_at)}`
        : "",
      h.reason?.includes("PM10")
        ? `PM10 ${formatTime(h.pollutant_times?.pm10 || h.observed_at)}`
        : "",
    ]
      .filter(Boolean)
      .join(" · ");
    return {
      latitude: h.latitude,
      longitude: h.longitude,
      title: `Potential hotspot · ${h.station}`,
      subtitle: `${h.city} · ${h.reason} · ${times}`,
      status: "pending",
    };
  });
  return (
    <>
      <PanelTitle
        eyebrow="NATIONAL MONITORING NETWORK"
        title="India pollution map"
        description="Explore station locations and recent stored readings across India. Orange markers identify simple threshold-based screening flags."
        action={
          <button className="btn btn-quiet" onClick={load} disabled={busy}>
            <RefreshCw size={15} className={busy ? "spin" : ""} /> Refresh map
          </button>
        }
      />
      {error && <div className="inline-warning">{error}</div>}
      <div className="station-summary-row">
        <div className="panel station-count-panel">
          <div className="eyebrow">KNOWN MONITORING STATIONS</div>
          <strong>{network?.count ?? "—"}</strong>
          <p>Directory entries; some stations may not have a recent reading</p>
          <span className="status-line">
            Directory sync: {formatTime(network?.directory_synced_at)} · Last
            provider fetch: {formatTime(network?.last_collected_at)}
          </span>
        </div>
        <div className="panel station-count-panel">
          <div className="eyebrow">THRESHOLD FLAGS</div>
          <strong>{hotspots.length}</strong>
          <p>Recent PM2.5 / PM10 screening flags</p>
          <span className="status-line">
            <TriangleAlert size={14} /> Not verified incidents
          </span>
        </div>
      </div>
      <section className="panel station-map-panel">
        <div className="panel-heading">
          <div>
            <div className="eyebrow">INDIA · OPENSTREETMAP</div>
            <h3>Monitoring locations and potential hotspots</h3>
            <p>{network?.note || "Waiting for stored station records."}</p>
          </div>
          <MapPinned size={20} />
        </div>
        <MapView
          center={[22.5, 79]}
          zoom={5}
          markers={[...stationMarkers, ...hotspotMarkers]}
        />
        <p className="chart-footnote">
          {hotspots.length
            ? hotspots.length + " threshold flags"
            : "No threshold flags returned"}
          . Station points reflect the latest stored observation per station,
          not necessarily a live feed.
        </p>
      </section>
      <section className="panel station-list-panel">
        <div className="panel-heading">
          <div>
            <div className="eyebrow">RECENTLY STORED NETWORK</div>
            <h3>Station directory</h3>
            <p>
              The map includes up to 5,000 station entries; this list shows the
              first 100.
            </p>
          </div>
        </div>
        <div className="station-list">
          {(network?.stations || []).slice(0, 100).map((s) => (
            <article
              className="station-row"
              key={`${s.source}-${s.station_id}`}
            >
              <div className="station-marker">
                <MapPinned size={18} />
              </div>
              <div className="station-details">
                <h4>{s.name}</h4>
                <p>
                  {s.city}
                  {s.state ? `, ${s.state}` : ""} · {s.source}
                </p>
                <small>
                  Latest reading: {formatTime(s.observed_at)} · Directory seen:{" "}
                  {formatTime(s.directory_seen_at)}
                </small>
              </div>
              <div className="station-values">
                {Object.entries(s.pollutants || {}).map(([k, v]) => (
                  <span key={k}>
                    <b>{k.toUpperCase()}</b>
                    {Number(v).toFixed(1)}
                    <small>
                      {formatTime(s.pollutant_times?.[k] || s.observed_at)}
                    </small>
                  </span>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}
