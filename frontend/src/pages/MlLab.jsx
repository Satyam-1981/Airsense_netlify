import { useEffect, useState } from "react";
import {
  BrainCircuit,
  FlaskConical,
  RefreshCw,
  Scale,
  Sparkles,
} from "lucide-react";
import PanelTitle from "../components/PanelTitle";
import { api } from "../api";
import { pollutantLabel, pollutantUnit } from "../utils";

const fields = ["pm25", "pm10", "no2", "so2", "co", "o3"];
const blank = { pm25: "", pm10: "", no2: "", so2: "", co: "", o3: "" };

export default function MlLab({ currentPollutants }) {
  const [values, setValues] = useState(blank);
  const [result, setResult] = useState(null);
  const [sensitivity, setSensitivity] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setValues(
      Object.fromEntries(
        fields.map((key) => [
          key,
          Number.isFinite(currentPollutants?.[key])
            ? String(currentPollutants[key])
            : "",
        ]),
      ),
    );
  }, [currentPollutants]);
  useEffect(() => {
    api
      .metrics()
      .then(setMetrics)
      .catch(() => setMetrics(null));
  }, []);

  const payload = () =>
    Object.fromEntries(
      fields
        .map((key) => [
          key,
          values[key].trim() === "" ? null : Number(values[key]),
        ])
        .filter(([, value]) => value !== null),
    );
  async function run(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setSensitivity(null);
    try {
      const input = payload();
      const [prediction, scenarios] = await Promise.all([
        api.predict(input),
        api.sensitivity(input),
      ]);
      setResult(prediction);
      setSensitivity(scenarios);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PanelTitle
        eyebrow="TRANSPARENT MACHINE LEARNING"
        title="Inside the AtmoIQ model."
        description="Explore the weighted ensemble, compare its predictions and see how changing one pollutant at a time affects the estimate."
      />
      <div className="model-overview-grid">
        <div className="model-overview panel">
          <div className="model-overview-icon">
            <BrainCircuit size={22} />
          </div>
          <div className="eyebrow">ENSEMBLE REGRESSOR</div>
          <h2>
            Three models.
            <br />
            <i>One estimate.</i>
          </h2>
          <p>
            Random Forest, Gradient Boosting and K-Nearest Neighbors are
            combined using weights selected on a validation split.
          </p>
          <div className="model-chip-row">
            <span>Random Forest</span>
            <span>Gradient Boosting</span>
            <span>KNN</span>
          </div>
        </div>
        <div className="model-metrics panel">
          <div className="panel-heading">
            <div>
              <div className="eyebrow">HELD-OUT EVALUATION</div>
              <h3>Training metrics</h3>
            </div>
            <Scale size={19} />
          </div>
          {metrics?.test_metrics?.weighted_ensemble ? (
            <div className="metric-pair-grid">
              <div>
                <span>RMSE</span>
                <b>{metrics.test_metrics.weighted_ensemble.rmse.toFixed(2)}</b>
              </div>
              <div>
                <span>MAE</span>
                <b>{metrics.test_metrics.weighted_ensemble.mae.toFixed(2)}</b>
              </div>
              <div>
                <span>R²</span>
                <b>{metrics.test_metrics.weighted_ensemble.r2.toFixed(3)}</b>
              </div>
              <div>
                <span>Training rows</span>
                <b>{Number(metrics.rows).toLocaleString("en-IN")}</b>
              </div>
            </div>
          ) : (
            <div className="empty-state compact">
              <p>Train the model to generate evaluation metrics.</p>
            </div>
          )}
        </div>
      </div>

      <section className="panel prediction-lab">
        <div className="panel-heading">
          <div>
            <div className="eyebrow">TRY A PREDICTION</div>
            <h3>Pollutant input lab</h3>
            <p>
              Current city readings are prefilled when available. You can change
              the values.
            </p>
          </div>
          <FlaskConical size={20} />
        </div>
        <form onSubmit={run}>
          <div className="pollutant-input-grid">
            {fields.map((key) => (
              <label className="field-label" key={key}>
                {pollutantLabel(key)} <small>{pollutantUnit(key)}</small>
                <input
                  type="number"
                  min="0"
                  step="any"
                  value={values[key]}
                  onChange={(event) =>
                    setValues((old) => ({ ...old, [key]: event.target.value }))
                  }
                  placeholder="Enter value"
                />
              </label>
            ))}
          </div>
          <div className="form-actions">
            <button type="submit" className="btn btn-primary" disabled={busy}>
              {busy ? "Running model…" : "Predict AQI"}
              <Sparkles size={15} />
            </button>
          </div>
        </form>
        {error && <div className="inline-warning">{error}</div>}
        {result && (
          <div className="prediction-result">
            <div className="prediction-number">
              <span>ENSEMBLE AQI PROXY</span>
              <strong>{result.aqi}</strong>
              <em>{result.category}</em>
            </div>
            <div className="prediction-details">
              <div>
                <span>Model spread</span>
                <b>{result.model_spread} AQI points</b>
                <small>{result.model_agreement}</small>
              </div>
              <div>
                <span>Input completeness</span>
                <b>{result.input_completeness}</b>
                <small>Number of supplied pollutants</small>
              </div>
              <div>
                <span>Held-out proxy RMSE</span>
                <b>{result.held_out_proxy_rmse ?? "—"}</b>
                <small>Test-set error, not a confidence interval</small>
              </div>
              <div>
                <span>Model version</span>
                <b>{result.model_version}</b>
              </div>
            </div>
            <div className="base-model-grid">
              {Object.entries(result.base_models).map(([name, value]) => (
                <div key={name}>
                  <span>{name.replaceAll("_", " ")}</span>
                  <strong>{value.toFixed(1)}</strong>
                  <small>
                    Weight {(result.weights[name] * 100).toFixed(1)}%
                  </small>
                </div>
              ))}
            </div>
            <p className="chart-footnote">
              Model disagreement and input completeness are descriptive
              reliability indicators, not calibrated prediction probabilities.{" "}
              {result.target_note}
            </p>
          </div>
        )}
      </section>

      {sensitivity && (
        <section className="panel sensitivity-panel">
          <div className="panel-heading">
            <div>
              <div className="eyebrow">WHAT-IF ANALYSIS</div>
              <h3>How sensitive is the estimate?</h3>
              <p>
                Each available pollutant is changed independently by −20% and
                +20%, then passed through the same trained ensemble.
              </p>
            </div>
            <Scale size={19} />
          </div>
          <div className="sensitivity-list">
            {sensitivity.items.map((item) => (
              <div className="sensitivity-row" key={item.pollutant}>
                <div>
                  <strong>{pollutantLabel(item.pollutant)}</strong>
                  <small>
                    Baseline {item.baseline_value.toFixed(2)}{" "}
                    {pollutantUnit(item.pollutant)}
                  </small>
                </div>
                <div className="sensitivity-delta">
                  <span
                    className={item.lower_delta > 0 ? "negative" : "positive"}
                  >
                    {item.lower_delta > 0 ? "+" : ""}
                    {item.lower_delta}
                  </span>
                  <small>−20%</small>
                </div>
                <div className="sensitivity-delta">
                  <span
                    className={item.upper_delta > 0 ? "negative" : "positive"}
                  >
                    {item.upper_delta > 0 ? "+" : ""}
                    {item.upper_delta}
                  </span>
                  <small>+20%</small>
                </div>
              </div>
            ))}
          </div>
          <p className="chart-footnote">{sensitivity.method}</p>
        </section>
      )}
      <div className="disclaimer">
        <strong>Research transparency</strong>
        <p>
          The model is trained on CPCB-breakpoint proxy labels derived from
          Open-Meteo CAMS pollutant data, not on matched official CPCB station
          AQI labels. Training metrics describe agreement with those proxy
          labels only. The model is not yet a validated official AQI forecast.
        </p>
      </div>
    </>
  );
}
