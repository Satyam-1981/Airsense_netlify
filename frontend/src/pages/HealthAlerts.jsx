import { useEffect, useState } from "react";
import { Bell, BellRing, HeartPulse, ShieldCheck, VolumeX } from "lucide-react";
import PanelTitle from "../components/PanelTitle";
import { getHealthAdvice } from "../utils";
import { api } from "../api";

const groups = [
  [
    "General public",
    "Reduce strenuous outdoor activity as air quality worsens. Keep track of local advisories.",
  ],
  [
    "Children",
    "Consider shorter or less strenuous outdoor play when pollution is elevated.",
  ],
  [
    "Older adults",
    "Reduce prolonged outdoor exertion during poor air quality and seek medical advice for symptoms.",
  ],
  [
    "People with asthma or heart conditions",
    "Follow your clinician's action plan and prescribed treatment. Avoid high-exposure periods when possible.",
  ],
];

export default function HealthAlerts({ city, prediction }) {
  const [threshold, setThreshold] = useState(100);
  const [enabled, setEnabled] = useState(false);
  const [quiet, setQuiet] = useState(false);
  const [status, setStatus] = useState("Alerts are off on this device.");
  const [notifyOnRise, setNotifyOnRise] = useState(true);
  const [serverAdvice, setServerAdvice] = useState(null);
  const advice = serverAdvice?.advice?.length
    ? serverAdvice.advice
    : getHealthAdvice(prediction?.category);

  useEffect(() => {
    if (!Number.isFinite(prediction?.aqi)) {
      setServerAdvice(null);
      return;
    }
    api
      .advice(prediction.aqi)
      .then(setServerAdvice)
      .catch(() => setServerAdvice(null));
  }, [prediction?.aqi]);

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("atmoiq-alerts") || "{}");
      setThreshold(Number(saved.threshold) || 100);
      setEnabled(Boolean(saved.enabled));
      setQuiet(Boolean(saved.quiet));
      setNotifyOnRise(saved.notifyOnRise !== false);
    } catch {
      /* Use safe defaults for invalid local settings. */
    }
  }, []);

  useEffect(() => {
    if (
      !enabled ||
      quiet ||
      !prediction ||
      !("Notification" in window) ||
      Notification.permission !== "granted"
    )
      return;
    const lastKey = `atmoiq-last-aqi:${city.toLowerCase()}`;
    const storedPrevious = localStorage.getItem(lastKey);
    const previous = storedPrevious === null ? null : Number(storedPrevious);
    const current = prediction.aqi;
    const hasPrevious = Number.isFinite(previous);
    const crossed = hasPrevious && previous < threshold && current >= threshold;
    const firstHighReading = !hasPrevious && current >= threshold;
    const rose = notifyOnRise && hasPrevious && current - previous >= 30;
    if (crossed || firstHighReading || rose) {
      new Notification(`AtmoIQ · ${city}`, {
        body: `AQI estimate ${current} (${prediction.category}). Check current local advisories.`,
      });
    }
    localStorage.setItem(lastKey, String(current));
  }, [enabled, quiet, prediction, threshold, city, notifyOnRise]);

  async function enable() {
    if (!("Notification" in window)) {
      setStatus("This browser does not support notifications.");
      return;
    }
    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      setStatus("Notification permission was not granted.");
      return;
    }
    const updated = { threshold, enabled: true, quiet, notifyOnRise };
    localStorage.setItem("atmoiq-alerts", JSON.stringify(updated));
    setEnabled(true);
    setStatus("Device notifications are enabled while AtmoIQ is open.");
  }

  function save() {
    const updated = { threshold, enabled, quiet, notifyOnRise };
    localStorage.setItem("atmoiq-alerts", JSON.stringify(updated));
    setStatus("Alert preferences saved on this device.");
  }

  return (
    <>
      <PanelTitle
        eyebrow="PRACTICAL HEALTH GUIDANCE"
        title="Make the air easier to act on."
        description="Get clear precautions based on the current AQI estimate and set a personal threshold for pollution alerts."
      />
      <div className="health-summary panel">
        <div className="health-summary-icon">
          <HeartPulse size={23} />
        </div>
        <div>
          <span className="eyebrow">
            CURRENT GUIDANCE · {city.toUpperCase()}
          </span>
          <h2>{prediction?.category || "Waiting for AQI estimate"}</h2>
          <p>{advice[0]}</p>
          <small>{advice[1]}</small>
          {serverAdvice?.note && (
            <small className="field-help">{serverAdvice.note}</small>
          )}
        </div>
        <div className="health-summary-aqi">
          <span>MODELLED AQI</span>
          <strong>{prediction?.aqi ?? "—"}</strong>
        </div>
      </div>
      <div className="section-row">
        <div>
          <div className="eyebrow">GUIDANCE BY GROUP</div>
          <h2 className="section-title">Small steps that can help</h2>
        </div>
      </div>
      <div className="advice-grid">
        {groups.map(([name, text], index) => (
          <article className="panel advice-card" key={name}>
            <div className="advice-number">0{index + 1}</div>
            <h3>{name}</h3>
            <p>{text}</p>
          </article>
        ))}
      </div>
      <section className="panel alert-control">
        <div className="panel-heading">
          <div>
            <div className="eyebrow">PERSONAL AIR WATCH</div>
            <h3>Pollution threshold alerts</h3>
            <p>
              Notifications are generated on this device when a new AQI estimate
              is loaded. Provider updates may be less frequent than the page
              refresh.
            </p>
          </div>
          <BellRing size={21} />
        </div>
        <div className="alert-control-grid">
          <label className="field-label">
            Notify me at AQI
            <input
              type="number"
              min="1"
              max="500"
              value={threshold}
              onChange={(event) =>
                setThreshold(
                  Math.max(1, Math.min(500, Number(event.target.value) || 1)),
                )
              }
            />
          </label>
          <label className="toggle-line">
            <input
              type="checkbox"
              checked={notifyOnRise}
              onChange={(event) => setNotifyOnRise(event.target.checked)}
            />
            <span>Also alert if AQI rises by 30 or more between updates</span>
          </label>
          <label className="toggle-line">
            <input
              type="checkbox"
              checked={quiet}
              onChange={(event) => setQuiet(event.target.checked)}
            />
            <span>
              <VolumeX size={15} /> Quiet mode
            </span>
          </label>
        </div>
        <div className="alert-actions">
          <button className="btn btn-primary" onClick={enable}>
            <Bell size={15} /> Enable notifications
          </button>
          <button className="btn btn-quiet" onClick={save}>
            Save preferences
          </button>
        </div>
        <div className="alert-status">
          <ShieldCheck size={15} />
          {status}
        </div>
      </section>
      <div className="disclaimer">
        <strong>Important health note</strong>
        <p>
          Guidance follows the broad health-impact categories described by CPCB,
          but the AtmoIQ AQI shown here may be a model-derived proxy rather
          than an official station reading. This is general information, not
          medical advice. Check official CPCB or local health advisories for
          decisions. Notifications are browser-based, require permission and
          this application to remain open; they are not background push, SMS,
          emergency or official CPCB alerts.
        </p>
      </div>
    </>
  );
}
