import { useEffect, useState } from "react";
import { Clock3, Footprints, LockKeyhole, Trash2 } from "lucide-react";
import PanelTitle from "../components/PanelTitle";
import { api } from "../api";
import { getClientId, formatTime } from "../utils";

export default function Exposure({ city, prediction, pollutants }) {
  const [clientId] = useState(getClientId);
  const [records, setRecords] = useState([]);
  const [activity, setActivity] = useState("walking");
  const [duration, setDuration] = useState(30);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    try {
      const result = await api.exposure(clientId);
      setRecords(result.records || []);
    } catch (err) {
      setError(err.message);
    }
  }
  useEffect(() => {
    load();
  }, [clientId]);

  async function addEntry(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api.saveExposure({
        client_id: clientId,
        city,
        activity,
        duration_minutes: Number(duration),
        aqi: prediction?.aqi ?? null,
        pm25: pollutants?.pm25 ?? null,
      });
      setMessage("Your activity entry has been saved.");
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function clearHistory() {
    if (
      !window.confirm(
        "Delete all AtmoIQ exposure history saved for this browser?",
      )
    )
      return;
    setBusy(true);
    try {
      await api.deleteExposure(clientId);
      setRecords([]);
      setMessage("Your saved exposure history has been deleted.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PanelTitle
        eyebrow="YOUR PERSONAL LOG"
        title="Keep track of time spent outdoors."
        description="Save activities alongside the available area-level air-quality estimate to build a simple personal history."
      />
      <div className="exposure-intro panel">
        <div className="exposure-icon">
          <Footprints size={24} />
        </div>
        <div>
          <div className="eyebrow">
            AN ACTIVITY JOURNAL, NOT A MEDICAL MEASUREMENT
          </div>
          <h2>Make your day easier to look back on.</h2>
          <p>
            Log time spent walking, running or commuting and AtmoIQ will
            attach the current city estimate when it is available.
          </p>
        </div>
      </div>
      <div className="exposure-layout">
        <section className="panel exposure-form-panel">
          <div className="panel-heading">
            <div>
              <div className="eyebrow">NEW ENTRY</div>
              <h3>Log an outdoor activity</h3>
            </div>
            <Clock3 size={20} />
          </div>
          <form onSubmit={addEntry} className="stack-form">
            <label className="field-label">
              Location
              <input value={city} readOnly />
            </label>
            <label className="field-label">
              Activity
              <select
                value={activity}
                onChange={(event) => setActivity(event.target.value)}
              >
                <option value="walking">Walking</option>
                <option value="running">Running</option>
                <option value="cycling">Cycling</option>
                <option value="commuting">Commuting</option>
                <option value="outdoor_work">Outdoor work</option>
                <option value="other">Other</option>
              </select>
            </label>
            <label className="field-label">
              Time outdoors (minutes)
              <input
                type="number"
                min="1"
                max="720"
                value={duration}
                onChange={(event) => setDuration(event.target.value)}
              />
            </label>
            <div className="exposure-current">
              <span>Attached AQI estimate</span>
              <b>{prediction?.aqi ?? "Not available"}</b>
              <small>
                {prediction?.category || "No model result"} · PM2.5{" "}
                {Number.isFinite(pollutants?.pm25)
                  ? `${pollutants.pm25.toFixed(1)} µg/m³`
                  : "not available"}
              </small>
            </div>
            <button type="submit" className="btn btn-primary" disabled={busy}>
              Save activity
            </button>
          </form>
          {error && <div className="inline-warning">{error}</div>}
          {message && <div className="success-note">{message}</div>}
        </section>
        <section className="panel exposure-history-panel">
          <div className="panel-heading">
            <div>
              <div className="eyebrow">YOUR RECENT ENTRIES</div>
              <h3>Activity history</h3>
            </div>
            <button
              className="icon-action danger"
              onClick={clearHistory}
              disabled={busy}
              aria-label="Delete all history"
            >
              <Trash2 size={16} />
            </button>
          </div>
          {records.length ? (
            <div className="exposure-record-list">
              {records.map((record) => (
                <article className="exposure-record" key={record.id}>
                  <div className="exposure-record-symbol">
                    <Footprints size={17} />
                  </div>
                  <div className="exposure-record-main">
                    <b>
                      {record.activity.replaceAll("_", " ")} · {record.city}
                    </b>
                    <span>
                      {record.duration_minutes} minutes ·{" "}
                      {formatTime(record.recorded_at)}
                    </span>
                  </div>
                  <div className="exposure-record-aqi">
                    <b>{record.aqi ?? "—"}</b>
                    <small>AQI estimate</small>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="empty-state compact">
              <Footprints size={22} />
              <p>
                No activities logged yet. Entries are linked to a random ID
                saved in this browser; this is not an authenticated private
                account.
              </p>
            </div>
          )}
        </section>
      </div>
      <div className="privacy-note">
        <LockKeyhole size={17} />
        <div>
          <strong>Privacy and limitations</strong>
          <p>
            AtmoIQ does not require an account. A random browser ID links
            entries to this browser; there is no account login or identity
            verification. You can delete the linked records at any time. These
            entries pair activity duration with area-level readings; they are
            not personal dosimeter measurements, a dose calculation or a medical
            exposure assessment.
          </p>
        </div>
      </div>
    </>
  );
}
