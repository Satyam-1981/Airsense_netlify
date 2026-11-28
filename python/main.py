"""AirSense's single Python backend: data providers, AQI calculations and ML inference."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import joblib
import numpy as np
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

BASE = Path(__file__).resolve().parent
ARTIFACTS = BASE / "artifacts"
MODEL_PATH = ARTIFACTS / "airsense_models.joblib"
METRICS_PATH = ARTIFACTS / "metrics.json"
INDIA_TZ = ZoneInfo("Asia/Kolkata")
FEATURES = ["pm2_5", "pm10", "nitrogen_dioxide", "sulphur_dioxide", "carbon_monoxide", "ozone", "ammonia"]
HOURLY = ",".join(FEATURES)
CITIES = [
    {"name":"Kolkata","state":"West Bengal","lat":22.5726,"lon":88.3639},
    {"name":"Howrah","state":"West Bengal","lat":22.5958,"lon":88.2636},
    {"name":"Durgapur","state":"West Bengal","lat":23.5204,"lon":87.3119},
    {"name":"Asansol","state":"West Bengal","lat":23.6739,"lon":86.9524},
    {"name":"Siliguri","state":"West Bengal","lat":26.7271,"lon":88.3953},
    {"name":"Haldia","state":"West Bengal","lat":22.0667,"lon":88.0698},
    {"name":"Deoghar","state":"Jharkhand","lat":24.4854,"lon":86.6947},
    {"name":"Delhi","state":"Delhi","lat":28.6139,"lon":77.2090},
    {"name":"Mumbai","state":"Maharashtra","lat":19.0760,"lon":72.8777},
    {"name":"Bengaluru","state":"Karnataka","lat":12.9716,"lon":77.5946},
    {"name":"Chennai","state":"Tamil Nadu","lat":13.0827,"lon":80.2707},
    {"name":"Hyderabad","state":"Telangana","lat":17.3850,"lon":78.4867},
]

# (concentration low, high, AQI low, AQI high). CO is mg/m³; others µg/m³.
BREAKPOINTS = {
    "pm25": [(0,30,0,50),(30,60,50,100),(60,90,100,200),(90,120,200,300),(120,250,300,400),(250,500,400,500)],
    "pm10": [(0,50,0,50),(50,100,50,100),(100,250,100,200),(250,350,200,300),(350,430,300,400),(430,600,400,500)],
    "no2": [(0,40,0,50),(40,80,50,100),(80,180,100,200),(180,280,200,300),(280,400,300,400),(400,1000,400,500)],
    "so2": [(0,40,0,50),(40,80,50,100),(80,380,100,200),(380,800,200,300),(800,1600,300,400),(1600,2000,400,500)],
    "co": [(0,1,0,50),(1,2,50,100),(2,10,100,200),(10,17,200,300),(17,34,300,400),(34,50,400,500)],
    "o3": [(0,50,0,50),(50,100,50,100),(100,168,100,200),(168,208,200,300),(208,748,300,400),(748,1000,400,500)],
    "nh3": [(0,200,0,50),(200,400,50,100),(400,800,100,200),(800,1200,200,300),(1200,1800,300,400),(1800,2400,400,500)],
}
POLLUTANT_KEYS = {"pm25":"pm2_5", "pm10":"pm10", "no2":"nitrogen_dioxide", "so2":"sulphur_dioxide", "co":"carbon_monoxide", "o3":"ozone", "nh3":"ammonia"}

app = FastAPI(
    title="AirSense AQI API", version="3.0.0",
    description="Single Python API for AirSense. ML targets are CAMS-derived AQI proxies, not measured CPCB AQI."
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in os.getenv("CORS_ORIGINS", "*").split(",") if x.strip()],
    allow_credentials=False, allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["*"],
)
bundle = None


class Pollutants(BaseModel):
    pm25: Optional[float] = Field(None, ge=0, le=100000)
    pm10: Optional[float] = Field(None, ge=0, le=100000)
    no2: Optional[float] = Field(None, ge=0, le=100000)
    so2: Optional[float] = Field(None, ge=0, le=100000)
    co: Optional[float] = Field(None, ge=0, le=1000, description="mg/m³")
    o3: Optional[float] = Field(None, ge=0, le=100000)
    nh3: Optional[float] = Field(None, ge=0, le=100000)


def category(value: int) -> tuple[str, str]:
    if value <= 50: return "Good", "#20b77a"
    if value <= 100: return "Satisfactory", "#9acb3c"
    if value <= 200: return "Moderate", "#f2c94c"
    if value <= 300: return "Poor", "#f2994a"
    if value <= 400: return "Very Poor", "#eb5757"
    return "Severe", "#8e244d"


def advisory(value: int) -> list[str]:
    if value <= 50: return ["Everyone: Enjoy normal outdoor activities.", "Children and older adults: Normal activity is generally appropriate."]
    if value <= 100: return ["Sensitive people: Consider reducing prolonged, heavy outdoor exertion.", "General public: Unusually sensitive people may experience minor breathing discomfort."]
    if value <= 200: return ["Children, older adults and people with asthma or heart disease: Reduce prolonged outdoor exertion.", "General public: Consider reducing prolonged, heavy outdoor activity."]
    if value <= 300: return ["Sensitive groups: Avoid prolonged outdoor exertion; follow your clinician's action plan.", "General public: Reduce prolonged outdoor exertion and take more breaks."]
    if value <= 400: return ["Everyone: Avoid prolonged outdoor exertion; keep outdoor activity light.", "People with asthma or heart disease: Stay indoors when possible and follow medical advice."]
    return ["Everyone: Avoid outdoor physical activity; remain indoors with cleaner air where possible.", "Children, older adults and people with heart or lung conditions: Take extra precautions and seek medical advice if symptoms worsen."]


def sub_index(key: str, value: float) -> Optional[int]:
    if not np.isfinite(value) or value < 0: return None
    for lo, hi, ilo, ihi in BREAKPOINTS[key]:
        if lo <= value <= hi:
            return int(round((ihi - ilo) * (value - lo) / (hi - lo) + ilo))
    return 500


def normalized_values(p: Pollutants) -> dict:
    return p.model_dump()


def prediction(p: Pollutants) -> dict:
    values = normalized_values(p)
    present = {k: v for k, v in values.items() if v is not None}
    if not present:
        raise HTTPException(422, "Enter at least one pollutant concentration.")
    subindices = {k: sub_index(k, v) for k, v in present.items()}
    valid = {k: v for k, v in subindices.items() if v is not None}
    if len(valid) < 3 or not ({"pm25", "pm10"} & valid.keys()):
        raise HTTPException(422, "AQI requires at least three valid pollutants, including PM2.5 or PM10.")
    aqi = max(valid.values())
    dominant = max(valid, key=valid.get)
    weights = {"random_forest": 0.0, "gradient_boosting": 0.0, "knn": 0.0}
    base_models = {"random_forest": aqi, "gradient_boosting": aqi, "knn": aqi}
    model_name = "cpcb_breakpoint_calculation"
    if bundle is not None:
        feature_row = np.array([[values.get(k) if values.get(k) is not None else np.nan for k in bundle["features"]]], dtype=float)
        base_models = {k: float(m.predict(feature_row)[0]) for k, m in bundle["models"].items()}
        weights = bundle["weights"]
        aqi = int(np.clip(round(sum(base_models[k] * weights[k] for k in base_models)), 0, 500))
        model_name = "trained_scikit_learn_ensemble"
    name, color = category(aqi)
    completeness = round(len(present) / len(POLLUTANT_KEYS) * 100)
    limitations = [
        "The trained model target is a CPCB-breakpoint proxy derived from Open-Meteo CAMS modelled concentrations, not measured CPCB station AQI.",
        "Input completeness is not a calibrated prediction probability.",
        "For official reporting, use validated CPCB station observations and the applicable averaging windows.",
    ]
    if bundle is None:
        limitations.insert(0, "No trained model artifact is installed; this result is a transparent breakpoint calculation, not machine-learning inference.")
    return {
        "aqi": aqi, "category": name, "color": color, "confidence": completeness,
        "baseModels": {"randomForest": round(base_models["random_forest"]), "gradientBoosting": round(base_models["gradient_boosting"]), "knn": round(base_models["knn"])},
        "weights": {"randomForest": weights["random_forest"], "gradientBoosting": weights["gradient_boosting"], "knn": weights["knn"]},
        "pollutantSubindices": valid, "dominantPollutant": dominant.upper(), "advisory": advisory(aqi),
        "limitations": limitations, "model": model_name,
    }


def find_city(name: str) -> dict:
    q = name.strip().casefold()
    city = next((c for c in CITIES if c["name"].casefold() == q), None)
    if city is None:
        city = next((c for c in CITIES if q in c["name"].casefold()), None)
    if city is None:
        raise HTTPException(404, "City not found in the supported city list. Try Kolkata, Delhi, Mumbai, Bengaluru, Chennai, Hyderabad, or Deoghar.")
    return city


def fetch_open_meteo(city: dict, forecast_days: int = 5, past_days: int = 0) -> dict:
    params = {"latitude": city["lat"], "longitude": city["lon"], "hourly": HOURLY,
              "forecast_days": forecast_days, "past_days": past_days, "timezone": "Asia/Kolkata"}
    try:
        response = requests.get("https://air-quality-api.open-meteo.com/v1/air-quality", params=params, timeout=25)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise HTTPException(502, f"Air-quality provider unavailable: {exc}") from exc
    if not data.get("hourly", {}).get("time"):
        raise HTTPException(502, "Air-quality provider returned no hourly data.")
    return data


def row_from_hourly(hourly: dict, index: int) -> dict:
    def value(key: str):
        values = hourly.get(key) or []
        return values[index] if index < len(values) else None
    carbon_monoxide = value("carbon_monoxide")
    return {
        "pm25": value("pm2_5"), "pm10": value("pm10"),
        "no2": value("nitrogen_dioxide"), "so2": value("sulphur_dioxide"),
        "co": carbon_monoxide / 1000 if carbon_monoxide is not None else None,
        "o3": value("ozone"), "nh3": value("ammonia"),
    }


@app.on_event("startup")
def load_model():
    global bundle
    if MODEL_PATH.exists():
        try: bundle = joblib.load(MODEL_PATH)
        except Exception as exc: print(f"Could not load model artifact: {exc}")


@app.get("/")
def root(): return {"name": "AirSense API", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health():
    return {"ok": True, "model_loaded": bundle is not None, "mode": "trained_ensemble" if bundle is not None else "breakpoint_calculation", "version": app.version}


@app.get("/cities")
def cities(): return {"cities": CITIES}


@app.get("/air-quality/{city_name}")
def current_air_quality(city_name: str):
    city = find_city(city_name)
    hourly = fetch_open_meteo(city, forecast_days=5, past_days=1)["hourly"]
    now = datetime.now(INDIA_TZ).strftime("%Y-%m-%dT%H:%M")
    index = max((i for i, stamp in enumerate(hourly["time"]) if stamp <= now), default=0)
    pollutants = row_from_hourly(hourly, index)
    result = prediction(Pollutants(**pollutants))
    return {"city": city, "pollutants": pollutants, "observedAt": hourly["time"][index], "hourly": hourly,
            "source": "Open-Meteo CAMS modelled air-quality data", "prediction": result}


@app.post("/predict")
def predict(p: Pollutants): return prediction(p)


@app.post("/predict/batch")
def predict_batch(items: list[Pollutants]):
    if len(items) > 500: raise HTTPException(413, "Maximum 500 hourly records per request.")
    return [prediction(item) for item in items]


@app.get("/forecast/{city_name}")
def forecast(city_name: str):
    city = find_city(city_name)
    hourly = fetch_open_meteo(city, forecast_days=5)["hourly"]
    points = []
    for i, stamp in enumerate(hourly["time"]):
        pollutants = row_from_hourly(hourly, i)
        try: result = prediction(Pollutants(**pollutants))
        except HTTPException: result = {"aqi": None, "category": "Insufficient data", "color": "#8c9994"}
        points.append({"time": stamp, **result, "pm25": pollutants["pm25"], "pm10": pollutants["pm10"]})
    return {"city": city, "points": points, "source": "Open-Meteo CAMS forecast + " + ("trained Python ensemble" if bundle is not None else "CPCB breakpoint calculation")}


@app.get("/metrics")
def metrics():
    if not METRICS_PATH.exists():
        return {"trained": False, "metrics": None, "message": "No trained model metrics found. Run python train.py to train the ensemble."}
    data = json.loads(METRICS_PATH.read_text())
    return {"trained": bundle is not None, "metrics": data, "message": "Metrics from the held-out chronological test split. Targets are model-derived proxies, not observed CPCB labels."}


@app.get("/stations")
def stations(city: Optional[str] = None, state: Optional[str] = None):
    key = os.getenv("OPENAQ_API_KEY")
    if not key:
        return {"stations": [], "configured": False, "message": "OpenAQ API key not configured. Add OPENAQ_API_KEY to the Python service environment to enable station readings."}
    target = find_city(city) if city else None
    regional = [c for c in CITIES if c["state"].casefold() == (state or "").casefold()] if state else []
    centers = regional or ([target] if target else [None])
    headers = {"X-API-Key": key}
    locations = {}
    try:
        for center in centers:
            params = {"iso": "IN", "limit": 100, "page": 1}
            if center:
                params.update({"coordinates": f'{center["lat"]},{center["lon"]}', "radius": 25000})
            response = requests.get("https://api.openaq.org/v3/locations", params=params, headers=headers, timeout=20)
            response.raise_for_status()
            for item in response.json().get("results", []):
                item["_targetCity"] = center["name"] if center else ""
                locations[str(item["id"])] = item
    except requests.RequestException as exc:
        return {"stations": [], "configured": True, "message": f"OpenAQ location lookup failed: {exc}"}
    output = []
    for item in list(locations.values())[:30]:
        if state and state.casefold() not in str(item.get("state", state)).casefold(): continue
        pollutants = {}
        updated = (item.get("datetimeLast") or {}).get("utc") or "Not supplied"
        try:
            response = requests.get(f'https://api.openaq.org/v3/locations/{item["id"]}/latest', params={"limit":100,"page":1}, headers=headers, timeout=12)
            if response.ok:
                for reading in response.json().get("results", []):
                    param = str((reading.get("parameter") or {}).get("name") or "").lower().replace("₂", "2").replace("₃", "3").replace(".", "").replace("_", "")
                    value = reading.get("value")
                    if not isinstance(value, (int, float)): continue
                    keymap = {"pm25":"pm25", "pm2.5":"pm25", "pm10":"pm10", "no2":"no2", "nitrogendioxide":"no2", "so2":"so2", "sulfurdioxide":"so2", "sulphurdioxide":"so2", "o3":"o3", "ozone":"o3", "co":"co", "carbonmonoxide":"co", "nh3":"nh3", "ammonia":"nh3"}
                    dest = keymap.get(param)
                    if dest:
                        unit = reading.get("unit") or (reading.get("parameter") or {}).get("units")
                        pollutants[dest] = value / 1000 if dest == "co" and unit in ("µg/m³", "ug/m3") else value
                    stamp = (reading.get("datetime") or {}).get("utc")
                    if stamp and (updated == "Not supplied" or stamp > updated): updated = stamp
        except requests.RequestException: pass
        coords = item.get("coordinates") or {}
        output.append({"id":str(item["id"]), "name":item.get("name") or "Unnamed station", "city":item.get("locality") or item.get("city") or item.get("_targetCity") or "Unknown", "state":item.get("state") or "India", "source":"OpenAQ v3", "updatedAt":updated, "pollutants":pollutants, "lat":coords.get("latitude") or 0, "lon":coords.get("longitude") or 0})
    with_readings = sum(bool(x["pollutants"]) for x in output)
    return {"stations": output, "configured": True, "message": f"{len(output)} OpenAQ locations found; {with_readings} returned at least one latest sensor reading. Coverage depends on upstream reporting."}


@app.get("/cpcb-observations")
def cpcb_observations(limit: int = Query(50, ge=1, le=100)):
    key, resource = os.getenv("DATA_GOV_IN_API_KEY"), os.getenv("DATA_GOV_IN_RESOURCE_ID")
    if not key or not resource:
        return {"configured": False, "records": [], "message": "Set DATA_GOV_IN_API_KEY and DATA_GOV_IN_RESOURCE_ID after selecting the appropriate CPCB/air-quality resource on data.gov.in."}
    try:
        response = requests.get(f"https://api.data.gov.in/resource/{resource}", params={"api-key":key,"format":"json","limit":limit}, timeout=20)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        return {"configured": True, "records": [], "message": f"data.gov.in request failed: {exc}"}
    return {"configured": True, "records": payload.get("records", []), "fields": payload.get("field", []), "message": f"Loaded {len(payload.get('records', []))} records. Validate resource-specific fields, units and averaging semantics before using as reference AQI."}
