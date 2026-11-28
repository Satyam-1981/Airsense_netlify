import { useEffect, useState } from "react";
import {
  Camera,
  MapPin,
  RefreshCw,
  ShieldAlert,
  UploadCloud,
} from "lucide-react";
import PanelTitle from "../components/PanelTitle";
import MapView from "../components/MapView";
import { api } from "../api";
import { formatTime } from "../utils";

function localDateTime() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 16);
}

export default function Community({ city, location }) {
  const [reports, setReports] = useState([]);
  const [form, setForm] = useState({
    category: "smoke",
    description: "",
    city,
    latitude: "",
    longitude: "",
    observed_at: localDateTime(),
  });
  const [photo, setPhoto] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    setBusy(true);
    try {
      const result = await api.hotspots();
      setReports(result.reports || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    load();
  }, []);
  useEffect(
    () => setForm((old) => ({ ...old, city, latitude: "", longitude: "" })),
    [city],
  );

  function useLocation() {
    if (!navigator.geolocation) {
      setError("Location is not available in this browser.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) =>
        setForm((old) => ({
          ...old,
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        })),
      () => setError("Location permission was not granted."),
      { timeout: 10000 },
    );
  }

  async function submit(event) {
    event.preventDefault();
    setError("");
    setMessage("");
    const body = new FormData();
    Object.entries(form).forEach(([key, value]) =>
      body.append(
        key,
        key === "observed_at" ? new Date(value).toISOString() : String(value),
      ),
    );
    if (photo) body.append("photo", photo);
    setBusy(true);
    try {
      await api.submitHotspot(body);
      setMessage(
        "Thank you. Your report was received and is marked unverified until reviewed.",
      );
      setForm((old) => ({
        ...old,
        description: "",
        observed_at: localDateTime(),
      }));
      setPhoto(null);
      const input = document.getElementById("hotspot-photo");
      if (input) input.value = "";
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const mapMarkers = reports.map((report) => ({
    latitude: report.latitude,
    longitude: report.longitude,
    title: `${report.category} · ${report.city}`,
    subtitle: `${report.status_label} · Observed ${formatTime(report.observed_at)}`,
    status: report.status,
  }));

  return (
    <>
      <PanelTitle
        eyebrow="COMMUNITY OBSERVATIONS"
        title="Help make local air issues visible."
        description="Report visible smoke, dust or open burning near you. Reports stay unverified until reviewed by an administrator."
        action={
          <button className="btn btn-quiet" onClick={load} disabled={busy}>
            <RefreshCw size={15} className={busy ? "spin" : ""} /> Refresh
          </button>
        }
      />
      <section className="panel community-map-panel">
        <div className="panel-heading">
          <div>
            <div className="eyebrow">COMMUNITY MAP</div>
            <h3>Reported local pollution observations</h3>
            <p>
              Verified and unverified reports are shown with different markers.
              They are not official monitoring measurements.
            </p>
          </div>
          <MapPin size={19} />
        </div>
        <div className="map-legend">
          <span>
            <i className="map-legend-dot verified" /> Reviewed by AtmoIQ
            administrator
          </span>
          <span>
            <i className="map-legend-dot pending" /> Awaiting review
          </span>
        </div>
        <MapView
          center={[
            location?.latitude ?? reports[0]?.latitude ?? 22.5,
            location?.longitude ?? reports[0]?.longitude ?? 79,
          ]}
          markers={mapMarkers}
        />
      </section>
      <div className="community-grid">
        <section className="panel report-form-panel">
          <div className="panel-heading">
            <div>
              <div className="eyebrow">SUBMIT A LOCAL REPORT</div>
              <h3>What did you notice?</h3>
            </div>
            <Camera size={20} />
          </div>
          <form onSubmit={submit} className="stack-form">
            <label className="field-label">
              Report type
              <select
                value={form.category}
                onChange={(event) =>
                  setForm({ ...form, category: event.target.value })
                }
              >
                <option value="smoke">Smoke</option>
                <option value="dust">Dust</option>
                <option value="open_burning">Open burning</option>
                <option value="industrial">Industrial emissions</option>
                <option value="other">Other</option>
              </select>
            </label>
            <label className="field-label">
              City
              <input
                required
                maxLength="100"
                value={form.city}
                onChange={(event) =>
                  setForm({ ...form, city: event.target.value })
                }
              />
            </label>
            <div className="two-field-grid">
              <label className="field-label">
                Latitude
                <input
                  required
                  type="number"
                  min="-90"
                  max="90"
                  step="any"
                  value={form.latitude}
                  onChange={(event) =>
                    setForm({ ...form, latitude: event.target.value })
                  }
                />
              </label>
              <label className="field-label">
                Longitude
                <input
                  required
                  type="number"
                  min="-180"
                  max="180"
                  step="any"
                  value={form.longitude}
                  onChange={(event) =>
                    setForm({ ...form, longitude: event.target.value })
                  }
                />
              </label>
            </div>
            <button type="button" className="text-button" onClick={useLocation}>
              <MapPin size={14} /> Use my current location
            </button>
            <small className="field-help">
              Coordinates must describe the place you observed. AtmoIQ does
              not substitute the city centre for a report location.
            </small>
            <label className="field-label">
              When did you see it?
              <input
                required
                type="datetime-local"
                value={form.observed_at}
                onChange={(event) =>
                  setForm({ ...form, observed_at: event.target.value })
                }
              />
            </label>
            <label className="field-label">
              Description <small>Optional, up to 500 characters</small>
              <textarea
                rows="3"
                maxLength="500"
                value={form.description}
                onChange={(event) =>
                  setForm({ ...form, description: event.target.value })
                }
                placeholder="Describe what you observed without identifying people."
              />
            </label>
            <label className="upload-control" htmlFor="hotspot-photo">
              <UploadCloud size={19} />
              <span>
                <b>{photo?.name || "Add a photo (optional)"}</b>
                <small>JPEG, PNG or WebP · up to 5 MB</small>
              </span>
              <input
                id="hotspot-photo"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={(event) => setPhoto(event.target.files?.[0] || null)}
              />
            </label>
            <button className="btn btn-primary" type="submit" disabled={busy}>
              Submit report <ShieldAlert size={15} />
            </button>
          </form>
          {error && <div className="inline-warning">{error}</div>}
          {message && <div className="success-note">{message}</div>}
        </section>
        <section className="panel reports-panel">
          <div className="panel-heading">
            <div>
              <div className="eyebrow">RECENT COMMUNITY REPORTS</div>
              <h3>What people have reported</h3>
            </div>
            <ShieldAlert size={20} />
          </div>
          {reports.length ? (
            <div className="report-list">
              {reports.map((report) => (
                <article className="report-card" key={report.id}>
                  {report.photo_url && (
                    <img
                      src={report.photo_url}
                      alt="Community pollution report"
                    />
                  )}
                  <div className="report-card-main">
                    <div className="report-status">{report.status_label}</div>
                    <h4>
                      {report.category} · {report.city}
                    </h4>
                    <p>
                      {report.description ||
                        "No additional description provided."}
                    </p>
                    <small>Observed {formatTime(report.observed_at)}</small>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="empty-state compact">
              <ShieldAlert size={22} />
              <p>
                No reports have been submitted yet. Community reports will
                appear here after submission.
              </p>
            </div>
          )}
          <p className="chart-footnote">
            Community reports are observations, not verified pollution
            measurements. Do not use them as emergency, enforcement or official
            monitoring data.
          </p>
        </section>
      </div>
    </>
  );
}
