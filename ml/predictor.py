"""Load and run the trained AtmoIQ regression ensemble."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from django.core.cache import cache

FEATURES = [
    "pm2_5", "pm10", "nitrogen_dioxide", "sulphur_dioxide",
    "carbon_monoxide", "ozone",
]
MODEL_NAMES = ["random_forest", "gradient_boosting", "knn"]
POLLUTANT_KEYS = {
    "pm25": "pm2_5", "pm10": "pm10", "no2": "nitrogen_dioxide",
    "so2": "sulphur_dioxide", "co": "carbon_monoxide",
    "o3": "ozone",
}


def category(aqi: int) -> str:
    if aqi <= 50:
        return "Good"
    if aqi <= 100:
        return "Satisfactory"
    if aqi <= 200:
        return "Moderate"
    if aqi <= 300:
        return "Poor"
    if aqi <= 400:
        return "Very Poor"
    return "Severe"


def _bundle() -> dict[str, Any] | None:
    path = Path(settings.ML_ARTIFACT_PATH)
    if not path.exists():
        return None
    cache_key = f"atmoiq_model:{path}:{path.stat().st_mtime_ns}"
    bundle = cache.get(cache_key)
    if bundle is not None:
        return bundle
    try:
        candidate = joblib.load(path)
    except Exception as exc:
        raise RuntimeError("The trained model artifact could not be loaded. Re-run `python ml/train.py`.") from exc
    if (not isinstance(candidate, dict) or not {"models", "features", "weights"}.issubset(candidate)
            or not isinstance(candidate["models"], dict) or not isinstance(candidate["weights"], dict)):
        raise RuntimeError("The trained model artifact has an invalid structure.")
    if candidate["features"] != FEATURES or set(candidate["models"]) != set(MODEL_NAMES):
        raise RuntimeError("The trained model artifact does not match the current feature schema.")
    if set(candidate["weights"]) != set(MODEL_NAMES):
        raise RuntimeError("The trained model artifact has incomplete ensemble weights.")
    weights = np.asarray([candidate["weights"][name] for name in MODEL_NAMES], dtype=float)
    if not np.isfinite(weights).all() or (weights < 0).any() or not np.isclose(weights.sum(), 1.0, atol=1e-5):
        raise RuntimeError("The trained model artifact has invalid ensemble weights.")
    cache.set(cache_key, candidate, timeout=3600)
    return candidate


def model_metrics() -> dict[str, Any] | None:
    path = Path(settings.ML_METRICS_PATH)
    if not path.exists():
        return None
    try:
        metrics = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("The ML metrics file is missing or invalid. Re-run `python ml/train.py`.") from exc
    if not isinstance(metrics, dict) or metrics.get("features") != FEATURES:
        raise RuntimeError("The ML metrics file is incompatible with this feature set. Re-run `python ml/train.py`.")
    return metrics


def has_prediction_coverage(pollutants: dict[str, Any]) -> bool:
    # No median/zero imputation: all six CAMS Global inputs must be present.
    return all(
        isinstance(pollutants.get(key), (int, float, np.number))
        and not isinstance(pollutants.get(key), bool)
        and np.isfinite(pollutants[key]) and pollutants[key] >= 0
        for key in POLLUTANT_KEYS
    )


def predict_many(pollutant_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not pollutant_rows:
        return []
    feature_rows = []
    for row in pollutant_rows:
        if not has_prediction_coverage(row):
            raise ValueError("All six supported CAMS Global pollutant inputs are required. Missing values are not imputed.")
        if row.get("nh3") is not None:
            raise ValueError("NH3 is not supported by the CAMS Global city model. NH3 remains available only in station observations where reported.")
        for key in POLLUTANT_KEYS:
            value = row.get(key)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float, np.number))
                                      or not np.isfinite(value) or value < 0):
                raise ValueError(f"{key} must be a finite, non-negative number or null.")
        feature_rows.append({
            target: row.get(source)
            for source, target in POLLUTANT_KEYS.items()
        })
    bundle = _bundle()
    if bundle is None:
        raise RuntimeError("The ML model has not been trained. Run `python ml/train.py` first.")
    frame = pd.DataFrame(feature_rows, columns=FEATURES, dtype=float)
    raw_predictions = {
        name: np.asarray(bundle["models"][name].predict(frame), dtype=float)
        for name in MODEL_NAMES
    }
    if any(not np.isfinite(values).all() for values in raw_predictions.values()):
        raise RuntimeError("The trained model returned a non-finite prediction.")
    # CPCB-style AQI proxy is bounded to 0–500; keep model extrapolation inside
    # that published scale rather than returning an impossible AQI value.
    base_predictions = {name: np.clip(values, 0, 500) for name, values in raw_predictions.items()}
    weights = bundle["weights"]
    results = []
    metrics = model_metrics() or {}
    test_metrics = metrics.get("test_metrics")
    test_metrics = test_metrics if isinstance(test_metrics, dict) else {}
    ensemble_metrics = test_metrics.get("weighted_ensemble", {})
    ensemble_metrics = ensemble_metrics if isinstance(ensemble_metrics, dict) else {}
    rmse = ensemble_metrics.get("rmse")
    for index in range(len(pollutant_rows)):
        values = {name: float(base_predictions[name][index]) for name in MODEL_NAMES}
        spread = max(values.values()) - min(values.values())
        aqi = int(round(sum(values[name] * float(weights[name]) for name in MODEL_NAMES)))
        completeness = sum(
            isinstance(value, (int, float)) and np.isfinite(value) and value >= 0
            for key, value in pollutant_rows[index].items()
            if key in POLLUTANT_KEYS
        )
        if spread <= 20:
            agreement = "High model agreement"
        elif spread <= 50:
            agreement = "Moderate model agreement"
        else:
            agreement = "Low model agreement"
        results.append({
            "aqi": max(0, min(500, aqi)),
            "category": category(max(0, min(500, aqi))),
            "base_models": values,
            "weights": {key: float(weights[key]) for key in MODEL_NAMES},
            "model_version": bundle.get("model_version", "unversioned"),
            "model_spread": round(float(spread), 1),
            "model_agreement": agreement,
            "input_completeness": f"{completeness}/{len(POLLUTANT_KEYS)} supported model inputs supplied",
            "held_out_proxy_rmse": round(float(rmse), 2) if isinstance(rmse, (int, float)) else None,
            "target_note": "Approximate AQI proxy trained on six native 3-hour Open-Meteo CAMS Global inputs. PM/NO2/SO2 use 24-hour means; CO/O3 use a three-sample approximation to the CPCB 8-hour window. NH3 is unavailable in CAMS Global and excluded. Missing inputs are not imputed; outputs are bounded to 0–500 and are not validated against official CPCB station AQI labels.",
        })
    return results


def sensitivity(pollutants: dict[str, Any]) -> dict[str, Any]:
    if not has_prediction_coverage(pollutants):
        raise ValueError("All six supported CAMS Global pollutant inputs are required. Missing values are not imputed.")
    features = [key for key, value in pollutants.items()
                if key in POLLUTANT_KEYS and isinstance(value, (int, float, np.number))
                and not isinstance(value, bool) and np.isfinite(value) and value >= 0]
    scenarios = [pollutants]
    indexes = []
    for feature in features:
        value = float(pollutants[feature])
        lower_index = len(scenarios)
        scenarios.append({**pollutants, feature: round(value * 0.8, 6)})
        upper_index = len(scenarios)
        scenarios.append({**pollutants, feature: round(value * 1.2, 6)})
        indexes.append((feature, value, lower_index, upper_index))
    predictions = predict_many(scenarios)
    baseline = predictions[0]["aqi"]
    items = []
    for feature, value, lower_index, upper_index in indexes:
        low = predictions[lower_index]["aqi"]
        high = predictions[upper_index]["aqi"]
        items.append({"pollutant": feature, "baseline_value": value, "lower_aqi": low, "upper_aqi": high, "lower_delta": low - baseline, "upper_delta": high - baseline})
    return {"baseline_aqi": baseline, "items": items, "method": "One-pollutant-at-a-time ±20% sensitivity analysis. It is not a causal explanation."}
