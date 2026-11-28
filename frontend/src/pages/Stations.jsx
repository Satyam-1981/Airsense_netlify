import { useEffect, useState } from "react";
import {
  LocateFixed,
  MapPin,
  RadioTower,
  RefreshCw,
  Signal,
  SignalZero,
} from "lucide-react";
import PanelTitle from "../components/PanelTitle";
import MapView from "../components/MapView";
import { api } from "../api";
import { formatTime, pollutantLabel, pollutantUnit } from "../utils";

export default function Stations({ city, location }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [gpsCoords, setGpsCoords] = useState(null);

  async function load(coords = undefined, usePreciseLocation = false) {
    setBusy(true);
    setError("");
    try {
      const selected = coords === undefined ? gpsCoords : coords;
      const result = await api.stations({
        city: usePreciseLocation ? "" : city,
        lat: selected?.lat ?? location?.latitude,
        lon: selected?.lon ?? location?.longitude,
      });
      setData(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    setGpsCoords(null);
    const cityCoords =
      Number.isFinite(location?.latitude) &&
      Number.isFinite(location?.longitude)
        ? { lat: location.latitude, lon: location.longitude }
        : null;
    load(cityCoords);
  }, [city, location?.latitude, location?.longitude]);

  useEffect(() => {
    const timer = window.setInterval(
      () => load(gpsCoords, Boolean(gpsCoords)),
      5 * 60 * 1000,
    );
    return () => window.clearInterval(timer);
  }, [city, location?.latitude, location?.longitude, gpsCoords]);

  function locateMe() {
    if (!navigator.geolocation) {
      setError("This browser does not provide location access.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const selected = {
          lat: position.coords.latitude,
          lon: position.coords.longitude,
        };
        setGpsCoords(selected);
        load(selected, true);
      },
      () => {
        setGpsCoords(null);
        setError(
          "Location permission was not granted. Showing stations around the selected city instead.",
        );
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 },
    );
  }

  const nearest = data?.nearest;
  const mapMarkers = (data?.stations || []).map((station) => ({
    latitude: station.latitude,
    longitude: station.longitude,
    title: station.name,
    subtitle: `${station.source} · ${station.distance_km.toFixed(1)} km · ${
      Object.entries(station.pollutants || {})
        .map(
          ([key, value]) =>
            `${key.toUpperCase()} ${value} at ${formatTime(station.pollutant_times?.[key] || station.observed_at)}`,
        )
        .join(" · ") || `Latest update ${formatTime(station.observed_at)}`
    }`,
  }));
  return (
    <>
      <PanelTitle
        eyebrow="GROUND-LEVEL CONTEXT"
        title="Monitoring stations near you"
        description="Find nearby monitoring locations, compare their latest published readings and check how recent the data is."
        action={
          <div className="heading-actions">
            <button className="btn btn-quiet" onClick={locateMe}>
              <LocateFixed size={15} /> Use my location
            </button>
            <button
              className="btn btn-quiet"
              onClick={() => load(undefined, Boolean(gpsCoords))}
              disabled={busy}
            >
              <RefreshCw size={15} className={busy ? "spin" : ""} />
            </button>
          </div>
        }
      />
      <div className="station-summary-row">
        <div className="panel nearest-panel">
          <div className="nearest-icon">
            <RadioTower size={21} />
          </div>
          <div className="eyebrow">CLOSEST AVAILABLE STATION</div>
          <h2>{nearest?.name || "No nearby station found"}</h2>
          <p>
            {nearest
              ? `${nearest.city}${nearest.state ? `, ${nearest.state}` : ""} · ${nearest.distance_km.toFixed(1)} km away`
              : "Try another city or configure the optional station provider API keys."}
          </p>
          {nearest && (
            <div className="nearest-meta">
              <span>{nearest.source}</span>
              <span>Updated {formatTime(nearest.observed_at)}</span>
            </div>
          )}
        </div>
        <div className="panel station-count-panel">
          <div className="eyebrow">AVAILABLE LOCATIONS</div>
          <strong>{data?.stations?.length ?? "—"}</strong>
          <p>Stations returned by configured providers</p>
          <span className="status-line">
            <span className="pulse-dot" />{" "}
            {busy
              ? "Refreshing stations"
              : `Last checked by AtmoIQ: ${formatTime(data?.fetched_at)}`}
          </span>
        </div>
      </div>
      {error && <div className="inline-warning">{error}</div>}
      <section className="panel station-map-panel">
        <div className="panel-heading">
          <div>
            <div className="eyebrow">NEARBY ON THE MAP</div>
            <h3>Monitoring locations around {data?.city?.name || city}</h3>
            <p>
              Select a marker to see station details. Map distances are
              straight-line estimates.
            </p>
          </div>
          <MapPin size={19} />
        </div>
        <MapView
          center={[
            data?.city?.latitude ?? location?.latitude ?? 22.5,
            data?.city?.longitude ?? location?.longitude ?? 79,
          ]}
          markers={mapMarkers}
        />
      </section>
      <div className="panel station-list-panel">
        <div className="panel-heading">
          <div>
            <div className="eyebrow">NEARBY MONITORING NETWORK</div>
            <h3>Station readings</h3>
            <p>{data?.message || "Station results will appear here."}</p>
          </div>
          <Signal size={19} />
        </div>
        {data?.stations?.length ? (
          <div className="station-list">
            {data.stations.map((station) => (
              <article
                className="station-row"
                key={`${station.source}-${station.station_id}`}
              >
                <div className="station-marker">
                  <RadioTower size={19} />
                </div>
                <div className="station-details">
                  <h4>{station.name}</h4>
                  <p>
                    {station.city}
                    {station.state ? `, ${station.state}` : ""} ·{" "}
                    {station.source}
                  </p>
                  <small>{formatTime(station.observed_at)}</small>
                </div>
                <div className="station-distance">
                  <strong>{station.distance_km.toFixed(1)} km</strong>
                  <small>straight-line distance</small>
                </div>
                <div className="station-values">
                  {Object.keys(station.pollutants || {}).length ? (
                    Object.entries(station.pollutants).map(([key, value]) => (
                      <span key={key}>
                        <b>{pollutantLabel(key)}</b>
                        {Number(value).toFixed(1)}{" "}
                        <small>
                          {pollutantUnit(key)} ·{" "}
                          {formatTime(
                            station.pollutant_times?.[key] ||
                              station.observed_at,
                          )}
                        </small>
                      </span>
                    ))
                  ) : (
                    <em>No supported pollutant readings supplied</em>
                  )}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <SignalZero size={25} />
            <h3>No station data available</h3>
            <p>
              {data?.source_status?.errors?.length
                ? data.source_status.errors.join(" · ")
                : data?.source_status?.cpcb_configured ||
                    data?.source_status?.openaq_configured
                  ? "No matching stations were returned for this location."
                  : "CPCB and OpenAQ keys are optional. Add the keys in the backend environment to retrieve station readings. The Open-Meteo city feed remains available separately."}
            </p>
          </div>
        )}
      </div>
      <div className="disclaimer">
        <strong>Reading carefully</strong>
        <p>
          Distances are straight-line estimates, not travel distances. Station
          readings can have different reporting times and units. AtmoIQ skips
          pollutant conversions when the provider unit is ambiguous.
        </p>
      </div>
    </>
  );
}
