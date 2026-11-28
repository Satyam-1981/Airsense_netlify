from __future__ import annotations

from datetime import datetime, timedelta, timezone as utc_timezone
from math import asin, cos, isfinite, radians, sin, sqrt
from zoneinfo import ZoneInfo
import re

import requests
from django.conf import settings

IST = ZoneInfo("Asia/Kolkata")
HOURLY_FIELDS = ["pm2_5", "pm10", "nitrogen_dioxide", "sulphur_dioxide", "carbon_monoxide", "ozone"]
OPENAQ_PARAMETERS = {
    "pm25": "pm25", "pm2.5": "pm25", "pm2_5": "pm25", "pm2 5": "pm25", "pm10": "pm10",
    "no2": "no2", "nitrogen dioxide": "no2", "so2": "so2", "sulfur dioxide": "so2", "sulphur dioxide": "so2",
    "co": "co", "carbon monoxide": "co", "o3": "o3", "ozone": "o3", "nh3": "nh3", "ammonia": "nh3",
}


def _get_json(url: str, params: dict | None = None, headers: dict | None = None, timeout: int = 15) -> dict:
    response = requests.get(url, params=params, headers=headers, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise requests.RequestException("The data provider returned an unexpected response format.")
    return payload


def resolve_city(name: str) -> dict:
    query = name.strip()
    if not query or len(query) > 100:
        raise ValueError("Enter a valid city name.")
    payload = _get_json("https://geocoding-api.open-meteo.com/v1/search", {"name": query, "count": 10, "language": "en", "format": "json"}, timeout=10)
    results = payload.get("results")
    if not isinstance(results, list):
        results = []
    matches = [item for item in results if isinstance(item, dict) and item.get("country_code") == "IN"]
    if not matches:
        raise ValueError(f"No Indian city found for '{query}'. Try a different spelling.")
    chosen = matches[0]
    try:
        resolved = {"name": str(chosen["name"])[:100], "state": str(chosen.get("admin1", ""))[:100],
                    "latitude": float(chosen["latitude"]), "longitude": float(chosen["longitude"]), "country": "India"}
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("The city lookup returned incomplete coordinates. Try another city spelling.") from exc
    if not resolved["name"] or not isfinite(resolved["latitude"]) or not isfinite(resolved["longitude"]):
        raise ValueError("The city lookup returned invalid coordinates. Try another city spelling.")
    return resolved


def provider_datetime(value: str) -> datetime:
    """Parse provider timestamps as UTC; the API request explicitly uses UTC."""
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=utc_timezone.utc)
    return parsed.astimezone(utc_timezone.utc)


def native_cams_points(hourly: dict) -> dict:
    """Keep native 3-hour CAMS Global points; never treat interpolated hourly values as observations."""
    times = hourly.get("time") or []
    parsed = [provider_datetime(value) for value in times]
    if len(parsed) < 2:
        raise RuntimeError("CAMS Global did not return enough forecast timestamps.")
    intervals = sorted((parsed[i] - parsed[i - 1]).total_seconds() / 3600 for i in range(1, len(parsed)))
    median_interval = intervals[len(intervals) // 2]
    if median_interval <= 1.5:
        indices = [i for i, value in enumerate(parsed) if value.minute == 0 and value.second == 0 and value.hour % 3 == 0]
    elif median_interval <= 3.5:
        indices = list(range(len(parsed)))
    else:
        raise RuntimeError(f"Unexpected CAMS Global time step ({median_interval:.1f} hours); no values were interpolated.")
    if len(indices) < 2:
        raise RuntimeError("No native 3-hour CAMS Global timestamps were returned; hourly interpolated values were not used.")
    native_times = [parsed[i] for i in indices]
    value_arrays = {key: [values[i] for i in indices] for key, values in hourly.items()
                    if key != "time" and isinstance(values, list) and len(values) == len(times)}
    # Rebuild a regular 3-hour grid. Missing provider timestamps become None,
    # never a carried-forward or interpolated concentration.
    by_time = {value: position for position, value in enumerate(native_times)}
    grid_times = []
    cursor = native_times[0]
    while cursor <= native_times[-1]:
        grid_times.append(cursor)
        cursor += timedelta(hours=3)
    selected = {key: [values[by_time[value]] if value in by_time else None for value in grid_times]
                for key, values in value_arrays.items()}
    selected["time"] = [value.isoformat() for value in grid_times]
    return selected


def fetch_hourly(city: dict) -> dict:
    payload = _get_json("https://air-quality-api.open-meteo.com/v1/air-quality", {
        "latitude": city["latitude"], "longitude": city["longitude"],
        "hourly": ",".join(HOURLY_FIELDS), "forecast_days": 5, "past_days": 1,
        "timezone": "UTC", "domains": "cams_global",
    }, timeout=25)
    hourly = payload.get("hourly")
    if not hourly or not hourly.get("time"):
        raise RuntimeError("The air-quality provider returned no forecast data for this location.")
    return native_cams_points(hourly)


def _mean(values: list, end: int, window: int, minimum: int):
    if end + 1 < window:
        return None
    valid = [float(value) for value in values[end - window + 1:end + 1]
             if isinstance(value, (int, float)) and isfinite(float(value)) and value >= 0]
    return sum(valid) / len(valid) if len(valid) >= minimum else None


def _max_8h(values: list, end: int):
    # CAMS Global is native 3-hourly. Three samples cover approximately 9 hours;
    # this is an explicitly approximate substitute for CPCB's 8-hour window.
    if end < 7:
        return None
    start = end - 7
    valid_24h = [v for v in values[start:end + 1]
                 if isinstance(v, (int, float)) and isfinite(float(v)) and v >= 0]
    if len(valid_24h) < 6:
        return None
    candidates = []
    for stop in range(start + 2, end + 1):
        average = _mean(values, stop, 3, 3)
        if average is not None and stop - 2 >= start:
            candidates.append(average)
    return max(candidates) if candidates else None


def pollutants_at(hourly: dict, index: int) -> dict:
    result = {
        "pm25": _mean(hourly.get("pm2_5", []), index, 8, 6),
        "pm10": _mean(hourly.get("pm10", []), index, 8, 6),
        "no2": _mean(hourly.get("nitrogen_dioxide", []), index, 8, 6),
        "so2": _mean(hourly.get("sulphur_dioxide", []), index, 8, 6),
        "co": None,
        "o3": None,
        # CAMS Global does not provide NH3; station providers may still report it.
        "nh3": None,
    }
    co = _max_8h(hourly.get("carbon_monoxide", []), index)
    ozone = _max_8h(hourly.get("ozone", []), index)
    result["co"] = co / 1000 if co is not None else None  # Open-Meteo µg/m³ to CPCB-style mg/m³.
    result["o3"] = ozone
    return result


def local_time_from_provider(value: str) -> datetime:
    return provider_datetime(value).astimezone(IST)


def current_hour_index(hourly: dict) -> int:
    now = datetime.now(utc_timezone.utc)
    times = [provider_datetime(value) for value in hourly["time"]]
    available = [index for index, value in enumerate(times) if value <= now]
    if not available:
        raise RuntimeError("No current or previous model hour is available yet.")
    return available[-1]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    a = min(1.0, max(0.0, a))
    return 6371 * 2 * asin(sqrt(a))


def normalize_concentration(value, unit: str, pollutant: str):
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(numeric) or numeric < 0:
        return None
    unit = (unit or "").lower().replace("μ", "µ").replace("³", "3").replace(" ", "")
    if unit in {"µg/m3", "ug/m3", "microgram/m3", "micrograms/m3"}:
        return numeric / 1000 if pollutant == "co" else numeric
    if unit in {"mg/m3", "milligram/m3", "milligrams/m3"}:
        return numeric if pollutant == "co" else numeric * 1000
    # ppm and ppb conversions are intentionally skipped; the conversion needs
    # molecular weight and environmental conditions that may not be supplied.
    return None


def _parse_datetime(value):
    if not value:
        return None
    if isinstance(value, dict):
        value = value.get("utc") or value.get("local")
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=IST) if parsed.tzinfo is None else parsed
    except ValueError:
        for fmt in ("%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(str(value), fmt).replace(tzinfo=IST)
            except ValueError:
                pass
    return None


def _normalize_param(name: str) -> str | None:
    key = re.sub(r"[_-]+", " ", (name or "").lower()).strip()
    key = re.sub(r"\s+", " ", key)
    return OPENAQ_PARAMETERS.get(key)


def get_openaq_stations(latitude: float, longitude: float, city: str, state: str) -> list[dict]:
    if not settings.OPENAQ_API_KEY:
        return []
    headers = {"X-API-Key": settings.OPENAQ_API_KEY}
    payload = _get_json("https://api.openaq.org/v3/locations", {
        "coordinates": f"{latitude},{longitude}", "radius": 25000, "limit": 75, "page": 1,
    }, headers=headers, timeout=20)
    stations = []
    # OpenAQ v3 latest readings identify their sensor by sensorsId. Parameter
    # names and units come from the location's sensors endpoint; joining these
    # records avoids guessing pollutant types or silently assuming units.
    locations = payload.get("results")
    if not isinstance(locations, list):
        return []
    for location in locations[:10]:
        if not isinstance(location, dict):
            continue
        coords = location.get("coordinates") or {}
        if not isinstance(coords, dict):
            continue
        lat, lon = coords.get("latitude"), coords.get("longitude")
        if (not isinstance(lat, (int, float)) or not isinstance(lon, (int, float))
                or not isfinite(float(lat)) or not isfinite(float(lon))
                or abs(float(lat)) > 90 or abs(float(lon)) > 180):
            continue
        location_id = location.get("id")
        if not isinstance(location_id, int):
            continue
        try:
            sensor_payload = _get_json(
                f"https://api.openaq.org/v3/locations/{location_id}/sensors",
                {"limit": 100, "page": 1}, headers=headers, timeout=12,
            )
            latest_payload = _get_json(
                f"https://api.openaq.org/v3/locations/{location_id}/latest",
                {"limit": 100, "page": 1}, headers=headers, timeout=12,
            )
        except requests.RequestException:
            continue

        sensor_metadata = {}
        sensor_results = sensor_payload.get("results")
        if not isinstance(sensor_results, list):
            sensor_results = []
        for sensor in sensor_results:
            if not isinstance(sensor, dict):
                continue
            parameter = sensor.get("parameter") or {}
            if not isinstance(parameter, dict):
                continue
            sensor_id = sensor.get("id")
            key = _normalize_param(str(parameter.get("name") or ""))
            if isinstance(sensor_id, int) and key:
                sensor_metadata[sensor_id] = (key, str(parameter.get("units") or ""))

        # Keep the newest valid reading per pollutant and retain its own
        # timestamp. OpenAQ sensors at one location do not necessarily update
        # at the same time, so a single station timestamp would be misleading.
        latest_by_pollutant = {}
        latest_results = latest_payload.get("results")
        if not isinstance(latest_results, list):
            latest_results = []
        for item in latest_results:
            if not isinstance(item, dict):
                continue
            metadata = sensor_metadata.get(item.get("sensorsId"))
            if not metadata:
                continue
            key, unit = metadata
            value = normalize_concentration(item.get("value"), unit, key)
            dt = _parse_datetime(item.get("datetime"))
            if value is None or dt is None:
                continue
            previous = latest_by_pollutant.get(key)
            if previous is None or dt > previous["time"]:
                latest_by_pollutant[key] = {"value": value, "time": dt}
        pollutants = {key: item["value"] for key, item in latest_by_pollutant.items()}
        pollutant_times = {key: item["time"].isoformat() for key, item in latest_by_pollutant.items()}
        observed = max((item["time"] for item in latest_by_pollutant.values()), default=None)
        name = str(location.get("name") or location.get("locality") or f"OpenAQ station {location_id}")[:240]
        stations.append({
            "source": "OpenAQ", "station_id": str(location_id), "name": name,
            "city": str(location.get("locality") or city)[:100], "state": str(state)[:100],
            "latitude": float(lat), "longitude": float(lon), "observed_at": observed,
            "pollutants": pollutants, "pollutant_times": pollutant_times,
        })
    return stations


def get_cpcb_stations(city: str | None = None, state: str | None = None) -> list[dict]:
    if not settings.DATA_GOV_IN_API_KEY:
        return []
    params = {
        "api-key": settings.DATA_GOV_IN_API_KEY, "format": "json", "limit": 1000, "offset": 0,
    }
    if city:
        params["filters[city]"] = str(city).strip().replace(" ", "_")
    if state:
        params["filters[state]"] = state
    grouped = {}
    # The API commonly caps one response at 1,000 records. Page through the
    # available directory so a nationwide refresh is not limited to page one.
    for offset in range(0, 20000, 1000):
        params["offset"] = offset
        payload = _get_json(f"https://api.data.gov.in/resource/{settings.DATA_GOV_IN_RESOURCE_ID}", params, timeout=25)
        page = payload.get("records", [])
        if not isinstance(page, list):
            raise requests.RequestException("CPCB/data.gov.in returned an invalid records list.")
        for row in page:
            if not isinstance(row, dict):
                continue
            row_city = str(row.get("city", "")).strip().replace("_", " ")[:100]
            row_state = str(row.get("state", "")).strip().replace("_", " ")[:100]
            name = str(row.get("station", "")).strip()[:240]
            try:
                lat, lon = float(row.get("latitude")), float(row.get("longitude"))
            except (TypeError, ValueError):
                continue
            if not isfinite(lat) or not isfinite(lon) or abs(lat) > 90 or abs(lon) > 180:
                continue
            if not name or not row_city or (city and row_city.lower() != city.lower()):
                continue
            # Keep the database key within its field limit while retaining
            # station name and coordinates for stable identification.
            station_id = f"{row_state[:40]}|{row_city[:40]}|{name[:90]}|{lat:.5f}|{lon:.5f}"
            station = grouped.setdefault(station_id, {
                "source": "CPCB", "station_id": station_id, "name": name, "city": row_city,
                "state": row_state, "latitude": lat, "longitude": lon, "observed_at": None,
                "pollutants": {}, "pollutant_times": {},
            })
            observed = _parse_datetime(row.get("last_update"))
            if observed and (station["observed_at"] is None or observed > station["observed_at"]):
                station["observed_at"] = observed
            pollutant = _normalize_param(str(row.get("pollutant_id", "")))
            if pollutant:
                value = normalize_concentration(row.get("pollutant_avg"), row.get("pollutant_unit", ""), pollutant)
                previous_time = _parse_datetime(station.get("pollutant_times", {}).get(pollutant))
                if value is not None and observed and (previous_time is None or observed >= previous_time):
                    station["pollutants"][pollutant] = value
                    station.setdefault("pollutant_times", {})[pollutant] = observed.isoformat()
        if len(page) < 1000:
            break
    return list(grouped.values())
