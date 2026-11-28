from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from io import BytesIO
from math import isfinite
from statistics import median, pstdev
import json
import re

import requests
from PIL import Image, ImageOps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import F
from django.core.files.base import ContentFile
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods

from ml.predictor import category as aqi_category, has_prediction_coverage, model_metrics, predict_many, sensitivity
from .models import ExposureRecord, ForecastSnapshot, HotspotReport, MonitoringStation, StationObservation
from .providers import (
    IST, current_hour_index, fetch_hourly, get_cpcb_stations,
    get_openaq_stations, haversine_km, local_time_from_provider,
    pollutants_at, provider_datetime, resolve_city,
)


def _json_body(request):
    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("Request body must be valid JSON.")
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")
    return payload


def _error(message: str, status: int = 400):
    return JsonResponse({"error": message}, status=status)


def _safe_float(value, minimum=None, maximum=None):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(result) or (minimum is not None and result < minimum) or (maximum is not None and result > maximum):
        return None
    return result


def _city_from_request(request):
    city_name = request.GET.get("city", "").strip()
    lat = _safe_float(request.GET.get("lat"), -90, 90)
    lon = _safe_float(request.GET.get("lon"), -180, 180)
    if lat is not None and lon is not None:
        return {"name": city_name or "Current location", "state": "", "latitude": lat, "longitude": lon, "country": "India"}
    if not city_name:
        raise ValueError("Provide a city name or valid latitude and longitude.")
    return resolve_city(city_name)


def _pollutant_time(row, pollutant):
    """Return the timestamp for one pollutant, falling back only for older records."""
    value = (row.pollutant_times or {}).get(pollutant)
    if not value:
        return row.observed_at
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return timezone.make_aware(parsed, IST) if timezone.is_naive(parsed) else parsed
    except (TypeError, ValueError):
        return None


def _save_station(station):
    observed_at = station.get("observed_at")
    MonitoringStation.objects.update_or_create(
        source=station["source"], station_id=station["station_id"],
        defaults={"station_name": station["name"], "city": station.get("city", ""),
                  "state": station.get("state", ""), "latitude": station.get("latitude"),
                  "longitude": station.get("longitude")},
    )
    # Timestamp-free records belong in the directory, but cannot form reliable history.
    if observed_at is None:
        return
    if timezone.is_naive(observed_at):
        observed_at = timezone.make_aware(observed_at, IST)
    defaults = {
        "station_name": station["name"], "city": station.get("city", ""),
        "state": station.get("state", ""), "latitude": station.get("latitude"),
        "longitude": station.get("longitude"), "pollutants": station.get("pollutants", {}),
        "pollutant_times": station.get("pollutant_times", {}),
    }
    StationObservation.objects.update_or_create(
        source=station["source"], station_id=station["station_id"], observed_at=observed_at,
        defaults=defaults,
    )


@ensure_csrf_cookie
@require_GET
def csrf_token(request):
    return JsonResponse({"csrf": True})


@require_GET
def health(request):
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        database_ok = True
    except Exception:
        database_ok = False
    model_artifact_available = settings.ML_ARTIFACT_PATH.is_file()
    return JsonResponse({"ok": database_ok, "database": "connected" if database_ok else "unavailable",
                         "model_artifact_available": model_artifact_available},
                        status=200 if database_ok else 503)


@require_GET
def city_current(request):
    try:
        city = _city_from_request(request)
        hourly = fetch_hourly(city)
        index = current_hour_index(hourly)
        pollutants = pollutants_at(hourly, index)
        valid = has_prediction_coverage(pollutants)
        prediction = predict_many([pollutants])[0] if valid and settings.ML_ARTIFACT_PATH.exists() else None
        observed_at = local_time_from_provider(hourly["time"][index])
        return JsonResponse({
            "city": city, "pollutants": pollutants,
            "modelled_at": observed_at.isoformat(),
            "fetched_at": timezone.now().isoformat(),
            "source": "Open-Meteo CAMS Global modelled concentrations using native 3-hour points; 24-hour means and approximate CO/O3 8-hour windows",
            "data_status": "available" if valid else "insufficient",
            "prediction_status": "ready" if prediction else ("model_not_trained" if valid and not settings.ML_ARTIFACT_PATH.exists() else "insufficient_inputs"),
            "prediction": prediction,
            "message": ("AQI is a model-derived estimate, not an official CPCB station reading." if prediction
                        else "Pollutant coverage is insufficient for an AQI estimate." if not valid
                        else "Pollutant data is available, but the AtmoIQ ML model has not been trained yet."),
        })
    except (ValueError, requests.RequestException) as exc:
        return _error(str(exc), 400 if isinstance(exc, ValueError) else 502)
    except RuntimeError as exc:
        return _error(str(exc), 503)


@require_GET
def forecast(request):
    try:
        city = _city_from_request(request)
        hourly = fetch_hourly(city)
        start = current_hour_index(hourly)
        times = hourly["time"]
        rows = []
        eligible = []
        eligible_indexes = []
        for index in range(start, len(times)):
            pollutants = pollutants_at(hourly, index)
            row = {"time": local_time_from_provider(times[index]).isoformat(), "pollutants": pollutants, "aqi": None, "category": None, "model_spread": None}
            rows.append(row)
            if has_prediction_coverage(pollutants):
                eligible.append(pollutants)
                eligible_indexes.append(len(rows) - 1)
        if eligible and settings.ML_ARTIFACT_PATH.exists():
            predictions = predict_many(eligible)
            for index, prediction in zip(eligible_indexes, predictions):
                rows[index].update({
                    "aqi": prediction["aqi"], "category": prediction["category"],
                    "model_spread": prediction["model_spread"], "model_agreement": prediction["model_agreement"],
                })
            snapshots = []
            for row in rows:
                if row["aqi"] is None:
                    continue
                snapshots.append(ForecastSnapshot(
                    city=city["name"], state=city.get("state", ""), latitude=city["latitude"],
                    longitude=city["longitude"], forecast_at=provider_datetime(row["time"]),
                    predicted_aqi=row["aqi"], category=row["category"], pollutants=row["pollutants"],
                    model_version=predictions[0]["model_version"],
                ))
            if snapshots:
                ForecastSnapshot.objects.bulk_create(
                    snapshots, batch_size=200, update_conflicts=True,
                    unique_fields=["city", "forecast_at", "model_version"],
                    update_fields=["predicted_aqi", "category", "pollutants", "generated_at"],
                )
        now = timezone.now()
        future_rows = [(provider_datetime(row["time"]), row) for row in rows
                       if provider_datetime(row["time"]) > now]
        lowest_candidates = [(row["aqi"], dt, row) for dt, row in future_rows
                             if dt <= now + timedelta(hours=24) and row["aqi"] is not None]
        lowest_forecast_point = None
        if lowest_candidates:
            _, _, chosen_point = min(lowest_candidates, key=lambda item: item[0])
            lowest_forecast_point = {"time": chosen_point["time"], "aqi": chosen_point["aqi"],
                                     "category": chosen_point["category"]}

        horizons = []
        for horizon in (1, 3, 6, 24):
            target = now + timedelta(hours=horizon)
            candidate = None
            # Never interpolate a native 3-hour CAMS point to claim a 1-hour forecast.
            if horizon != 1:
                candidates = [(dt, row) for dt, row in future_rows
                              if abs((dt - target).total_seconds()) <= 1.5 * 3600]
                if candidates:
                    candidate = min(candidates, key=lambda item: item[0])
            candidate_dt, candidate_row = candidate if candidate else (None, None)
            horizons.append({
                "hours_ahead": horizon,
                "time": candidate_row["time"] if candidate_row else None,
                "actual_hours_ahead": round((candidate_dt - now).total_seconds() / 3600, 1) if candidate_dt else None,
                "aqi": candidate_row["aqi"] if candidate_row else None,
                "category": candidate_row["category"] if candidate_row else None,
                "pollutants": candidate_row["pollutants"] if candidate_row else None,
                "reason": ("CAMS Global is native 3-hourly; no independent 1-hour forecast is available." if horizon == 1
                           else "No valid native CAMS point is available within 1.5 hours of this target." if not candidate_row
                           else "The ML model has not been trained for this project yet." if not settings.ML_ARTIFACT_PATH.is_file()
                           else "All six supported pollutant inputs are not available at this forecast point." if candidate_row["aqi"] is None
                           else None),
            })
        return JsonResponse({
            "city": city, "hours": rows, "horizon_predictions": horizons,
            "fetched_at": timezone.now().isoformat(),
            "source": "Open-Meteo CAMS Global native 3-hour model points with AtmoIQ AQI proxy estimates",
            "lowest_forecast_point": lowest_forecast_point,
            "model_available": settings.ML_ARTIFACT_PATH.is_file(),
            "note": "CAMS Global is native 3-hourly at about 45 km resolution and is updated twice daily. AtmoIQ keeps only native 3-hour timestamps; it does not interpolate hourly values. Therefore an independent 1-hour AQI forecast is not available from this source. PM/NO2/SO2 use 24-hour means from 3-hour samples; CO/O3 use a three-sample approximation to the CPCB 8-hour window. These are modelled estimates, not official station forecasts or a safety guarantee. Missing inputs are not imputed.",
        })
    except (ValueError, requests.RequestException) as exc:
        return _error(str(exc), 400 if isinstance(exc, ValueError) else 502)
    except RuntimeError as exc:
        return _error(str(exc), 503)


@require_GET
def stations(request):
    try:
        city = _city_from_request(request)
        cpcb, stored_stations, openaq, errors = [], [], [], []
        if city["name"] == "Current location":
            # Use the already-synchronised national directory for GPS searches;
            # never download the entire CPCB feed for one nearby lookup.
            directory = MonitoringStation.objects.exclude(latitude__isnull=True).exclude(longitude__isnull=True)
            if directory.exists():
                latest_by_station = {
                    (row.source, row.station_id): row
                    for row in StationObservation.objects.exclude(observed_at__isnull=True).order_by("source", "station_id", "-observed_at").distinct("source", "station_id")
                }
                for station in directory[:5000]:
                    latest = latest_by_station.get((station.source, station.station_id))
                    stored_stations.append({
                        "source": station.source, "station_id": station.station_id, "name": station.station_name,
                        "city": station.city, "state": station.state, "latitude": station.latitude,
                        "longitude": station.longitude,
                        "observed_at": latest.observed_at if latest else None,
                        "pollutants": latest.pollutants if latest else {},
                        "pollutant_times": latest.pollutant_times if latest else {},
                    })
            else:
                errors.append("The nationwide station directory has not been synced yet. Run refresh_station_network first.")
        else:
            try:
                cpcb = get_cpcb_stations(city=city["name"])
            except requests.RequestException as exc:
                errors.append(f"CPCB: {exc}")
        try:
            openaq = get_openaq_stations(city["latitude"], city["longitude"], city["name"], city.get("state", ""))
        except requests.RequestException as exc:
            errors.append(f"OpenAQ: {exc}")
        unique = {}
        for station in cpcb + stored_stations + openaq:
            key = (station["source"], station["station_id"])
            unique[key] = station
        records = list(unique.values())
        freshly_fetched = {(station["source"], station["station_id"]) for station in cpcb + openaq}
        for station in records:
            if (station["source"], station["station_id"]) in freshly_fetched:
                _save_station(station)
            station["distance_km"] = round(haversine_km(city["latitude"], city["longitude"], station["latitude"], station["longitude"]), 2)
            station["observed_at"] = station["observed_at"].isoformat() if station.get("observed_at") else None
        records.sort(key=lambda row: row["distance_km"])
        return JsonResponse({
            "city": city, "stations": records[:50],
            "nearest": records[0] if records else None,
            "message": "Monitoring-station results are sorted by straight-line distance. Each pollutant keeps its own provider timestamp where available.",
            "fetched_at": timezone.now().isoformat(),
            "source_status": {"cpcb_configured": bool(settings.DATA_GOV_IN_API_KEY), "openaq_configured": bool(settings.OPENAQ_API_KEY), "errors": errors},
        })
    except (ValueError, requests.RequestException) as exc:
        return _error(str(exc), 400 if isinstance(exc, ValueError) else 502)


@require_http_methods(["POST"])
def predict(request):
    try:
        body = _json_body(request)
        pollutants = body.get("pollutants", body)
        if not isinstance(pollutants, dict):
            raise ValueError("Provide pollutant values as an object.")
        return JsonResponse(predict_many([pollutants])[0])
    except ValueError as exc:
        return _error(str(exc), 400)
    except RuntimeError as exc:
        return _error(str(exc), 503)


@require_http_methods(["POST"])
def sensitivity_analysis(request):
    try:
        body = _json_body(request)
        pollutants = body.get("pollutants", body)
        if not isinstance(pollutants, dict):
            raise ValueError("Provide pollutant values as an object.")
        return JsonResponse(sensitivity(pollutants))
    except ValueError as exc:
        return _error(str(exc), 400)
    except RuntimeError as exc:
        return _error(str(exc), 503)


@require_GET
def ml_metrics(request):
    try:
        metrics = model_metrics()
        if metrics is None:
            return _error("Model metrics are not available yet. Train the model first.", 404)
        return JsonResponse(metrics)
    except RuntimeError as exc:
        return _error(str(exc), 503)


@require_GET
def history(request):
    city = request.GET.get("city", "").strip()
    try:
        days = min(90, max(7, int(request.GET.get("days", "30"))))
    except (TypeError, ValueError):
        days = 30
    since = timezone.now() - timedelta(days=days)
    observations = StationObservation.objects.filter(observed_at__gte=since).order_by(F("fetched_at").desc(nulls_last=True), "-observed_at")
    forecasts = ForecastSnapshot.objects.filter(forecast_at__gte=since, generated_at__gte=since)
    if city:
        observations = observations.filter(city__iexact=city)
        forecasts = forecasts.filter(city__iexact=city)
    # A sensor can update independently of the other pollutants at a site.
    # Deduplicate by that pollutant's own timestamp so unchanged carried-forward
    # values are not counted again when another sensor reports.
    daily = defaultdict(dict)
    for row in observations.only("city", "source", "station_id", "station_name", "observed_at", "pollutants", "pollutant_times"):
        for pollutant, value in (row.pollutants or {}).items():
            pollutant_time = _pollutant_time(row, pollutant)
            if (isinstance(value, (int, float)) and isfinite(value) and value >= 0
                    and pollutant_time and pollutant_time >= since):
                day = timezone.localtime(pollutant_time).date().isoformat()
                bucket = daily[(day, pollutant, row.source, row.station_id, row.station_name)]
                if pollutant_time not in bucket:
                    bucket[pollutant_time] = float(value)
    series = []
    for (day, pollutant, source, station_id, station_name), samples in sorted(daily.items()):
        values = list(samples.values())
        series.append({"date": day, "pollutant": pollutant, "source": source, "station_id": station_id, "station": station_name, "average": round(sum(values) / len(values), 2), "samples": len(values)})
    forecast_rows = list(forecasts.values("city", "forecast_at", "predicted_aqi", "category", "model_version").order_by("forecast_at")[:1000])
    for row in forecast_rows:
        row["forecast_at"] = row["forecast_at"].isoformat()
    return JsonResponse({"days": days, "series": series, "forecasts": forecast_rows, "observation_count": observations.count(), "note": "Historical station trends include only observations AtmoIQ has actually retrieved and stored. Gaps mean no reading was available; values from different stations and sources are kept separated."})


def _anomaly_rows(city: str):
    since = timezone.now() - timedelta(days=30)
    records = StationObservation.objects.filter(observed_at__gte=since).exclude(pollutants={}).order_by(F("fetched_at").desc(nulls_last=True), "-observed_at")
    if city:
        records = records.filter(city__iexact=city)
    grouped = defaultdict(dict)
    for row in records:
        if not row.observed_at:
            continue
        for pollutant, value in (row.pollutants or {}).items():
            pollutant_time = _pollutant_time(row, pollutant)
            if (isinstance(value, (int, float)) and isfinite(value) and value >= 0
                    and pollutant_time and pollutant_time >= since):
                bucket = grouped[(row.source, row.station_id, row.station_name, row.city, pollutant)]
                if pollutant_time not in bucket:
                    bucket[pollutant_time] = float(value)
    alerts = []
    for (source, station_id, station_name, station_city, pollutant), samples in grouped.items():
        values = sorted(samples.items(), key=lambda item: item[0])
        if len(values) < 11:
            continue
        baseline = [value for _, value in values[:-1][-30:]]
        latest_time, latest_value = values[-1]
        # Do not present an old measurement as a current pollution spike.
        if latest_time < timezone.now() - timedelta(hours=72):
            continue
        center = median(baseline)
        deviations = [abs(value - center) for value in baseline]
        mad = median(deviations)
        scale = 1.4826 * mad if mad > 0 else pstdev(baseline)
        minimum_increases = {"pm25": 5.0, "pm10": 10.0, "no2": 10.0, "so2": 5.0, "co": 0.2, "o3": 10.0, "nh3": 10.0}
        threshold = max(minimum_increases.get(pollutant, 5.0), 3.5 * scale)
        increase = latest_value - center
        if increase > threshold:
            alerts.append({
                "source": source, "station_id": station_id, "station": station_name, "city": station_city,
                "pollutant": pollutant, "latest_value": round(latest_value, 2),
                "baseline_median": round(center, 2), "increase": round(increase, 2),
                "observed_at": latest_time.isoformat(), "method": "Robust baseline comparison (median and MAD); at least 10 historical readings required.",
            })
    return sorted(alerts, key=lambda item: item["increase"], reverse=True)


@require_GET
def anomalies(request):
    city = request.GET.get("city", "").strip()
    return JsonResponse({
        "city": city or None, "anomalies": _anomaly_rows(city),
        "note": "These are statistical spikes relative to each station's own stored history, not confirmed pollution events or identified sources. At least 10 prior observations are required, and the latest reading must be within 72 hours.",
    })


@require_http_methods(["GET", "POST"])
def hotspots(request):
    if request.method == "GET":
        reports = HotspotReport.objects.exclude(status=HotspotReport.Status.REJECTED)[:100]
        items = [{
            "id": str(row.id), "category": row.get_category_display(), "category_key": row.category,
            "description": row.description, "city": row.city, "latitude": row.latitude,
            "longitude": row.longitude, "observed_at": row.observed_at.isoformat(),
            "status": row.status, "status_label": "Unverified community report" if row.status == HotspotReport.Status.PENDING else "Verified report",
            "photo_url": request.build_absolute_uri(row.photo.url) if row.photo else None,
            "created_at": row.created_at.isoformat(),
        } for row in reports]
        return JsonResponse({"reports": items, "note": "New reports are unverified until reviewed by an administrator. Do not treat them as official incident reports."})

    try:
        category = request.POST.get("category", "other")
        city = request.POST.get("city", "").strip()[:100]
        description = request.POST.get("description", "").strip()[:500]
        latitude = _safe_float(request.POST.get("latitude"), -90, 90)
        longitude = _safe_float(request.POST.get("longitude"), -180, 180)
        observed_at = datetime.fromisoformat(request.POST.get("observed_at", "").replace("Z", "+00:00"))
        if timezone.is_naive(observed_at):
            observed_at = timezone.make_aware(observed_at, IST)
        if category not in HotspotReport.Category.values or not city or latitude is None or longitude is None:
            raise ValueError("Choose a report type, provide a city and valid coordinates.")
        if observed_at > timezone.now() + timedelta(minutes=5) or observed_at < timezone.now() - timedelta(days=14):
            raise ValueError("Report time must be within the last 14 days and cannot be in the future.")
        photo = request.FILES.get("photo")
        if photo:
            if photo.size > settings.MAX_UPLOAD_SIZE or photo.content_type not in {"image/jpeg", "image/png", "image/webp"}:
                raise ValueError("Photo must be JPEG, PNG or WebP and no larger than 5 MB.")
            try:
                image = Image.open(photo)
                image.verify()
                photo.seek(0)
                image = ImageOps.exif_transpose(Image.open(photo)).convert("RGB")
                image.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
                output = BytesIO()
                image.save(output, format="JPEG", quality=86, optimize=True)
                photo = ContentFile(output.getvalue(), name=f"hotspot-{timezone.now().strftime('%Y%m%d%H%M%S')}.jpg")
            except Exception:
                raise ValueError("The uploaded photo is not a valid image.")
        report = HotspotReport(
            category=category, city=city, description=description,
            latitude=latitude, longitude=longitude, observed_at=observed_at,
            photo=photo, status=HotspotReport.Status.PENDING,
        )
        report.save()
        return JsonResponse({"id": str(report.id), "status": report.status, "message": "Report received and marked unverified until reviewed."}, status=201)
    except (ValueError, ValidationError) as exc:
        return _error(str(exc), 400)


@require_http_methods(["GET", "POST", "DELETE"])
def exposure(request):
    if request.method == "GET":
        client_id = request.GET.get("client_id", "")
        if len(client_id) < 16 or len(client_id) > 80:
            return _error("A valid local client ID is required.")
        rows = ExposureRecord.objects.filter(client_id=client_id)[:200]
        return JsonResponse({"records": [{
            "id": str(row.id), "city": row.city, "activity": row.activity,
            "duration_minutes": row.duration_minutes, "aqi": row.aqi, "pm25": row.pm25,
            "recorded_at": row.recorded_at.isoformat(),
        } for row in rows], "note": "These are user-logged time and activity records paired with available area-level readings. They are not personal dosimeter measurements or a medical exposure assessment."})
    if request.method == "DELETE":
        client_id = request.GET.get("client_id", "")
        if len(client_id) < 16 or len(client_id) > 80:
            return _error("A valid local client ID is required.")
        deleted, _ = ExposureRecord.objects.filter(client_id=client_id).delete()
        return JsonResponse({"deleted": deleted})
    try:
        body = _json_body(request)
        client_id = str(body.get("client_id", ""))
        city = str(body.get("city", "")).strip()[:100]
        activity = str(body.get("activity", "walking"))
        duration = int(body.get("duration_minutes", 30))
        aqi = body.get("aqi")
        pm25 = body.get("pm25")
        if len(client_id) < 16 or len(client_id) > 80:
            raise ValueError("A valid local client ID is required.")
        if not city or activity not in {"walking", "running", "cycling", "commuting", "outdoor_work", "other"}:
            raise ValueError("Provide a city and valid activity.")
        if duration < 1 or duration > 720:
            raise ValueError("Duration must be between 1 and 720 minutes.")
        if aqi is not None:
            aqi = _safe_float(aqi, 0, 500)
            if aqi is None:
                raise ValueError("AQI must be a finite number between 0 and 500.")
        if pm25 is not None:
            pm25 = _safe_float(pm25, 0, 100000)
            if pm25 is None:
                raise ValueError("PM2.5 must be a finite non-negative concentration.")
        record = ExposureRecord.objects.create(
            client_id=client_id, city=city, activity=activity, duration_minutes=duration,
            aqi=int(aqi) if aqi is not None else None, pm25=float(pm25) if pm25 is not None else None,
            data_source="AtmoIQ modelled city estimate" if (aqi is not None or pm25 is not None) else "No reading attached",
        )
        return JsonResponse({"id": str(record.id), "message": "Exposure history entry saved."}, status=201)
    except (ValueError, TypeError) as exc:
        return _error(str(exc), 400)


@require_GET
def india_network(request):
    """Return the station directory plus each station's latest stored reading."""
    directory = MonitoringStation.objects.all()
    if not directory.exists():
        # Backward-compatible fallback for projects before the directory sync ran.
        directory_rows = StationObservation.objects.exclude(latitude__isnull=True).exclude(longitude__isnull=True).exclude(observed_at__isnull=True).order_by("source", "station_id", "-observed_at").distinct("source", "station_id")
        items = []
        for row in directory_rows[:5000]:
            items.append({"source": row.source, "station_id": row.station_id, "name": row.station_name,
                "city": row.city, "state": row.state, "latitude": row.latitude, "longitude": row.longitude,
                "observed_at": row.observed_at.isoformat() if row.observed_at else None, "pollutants": row.pollutants,
                "pollutant_times": row.pollutant_times, "directory_seen_at": None})
    else:
        latest_by_station = {
            (reading.source, reading.station_id): reading
            for reading in StationObservation.objects.exclude(observed_at__isnull=True).order_by("source", "station_id", "-observed_at").distinct("source", "station_id")
        }
        items = []
        for station in directory.all()[:5000]:
            latest = latest_by_station.get((station.source, station.station_id))
            items.append({"source": station.source, "station_id": station.station_id, "name": station.station_name,
                "city": station.city, "state": station.state, "latitude": station.latitude, "longitude": station.longitude,
                "observed_at": latest.observed_at.isoformat() if latest and latest.observed_at else None,
                "pollutants": latest.pollutants if latest else {},
                "pollutant_times": latest.pollutant_times if latest else {},
                "directory_seen_at": station.last_seen_at.isoformat() if station.last_seen_at else None})
    latest_fetch = StationObservation.objects.filter(fetched_at__isnull=False).order_by("-fetched_at").values_list("fetched_at", flat=True).first()
    directory_sync = MonitoringStation.objects.order_by("-last_seen_at").values_list("last_seen_at", flat=True).first()
    return JsonResponse({"stations": items, "count": len(items),
        "last_collected_at": latest_fetch.isoformat() if latest_fetch else None,
        "directory_synced_at": directory_sync.isoformat() if directory_sync else None,
        "note": "Map markers show known station locations, including stations without a recent reading. Reading timestamps are separate from directory sync time. Run refresh_station_network on a schedule to discover new CPCB stations and update observations."})

@require_GET
def detected_hotspots(request):
    """Simple, explainable threshold flags from recent station observations."""
    since = timezone.now() - timedelta(hours=36)
    records = StationObservation.objects.filter(observed_at__gte=since).exclude(latitude__isnull=True).exclude(longitude__isnull=True).order_by("source", "station_id", "-observed_at").distinct("source", "station_id")
    city = request.GET.get("city", "").strip()
    if city:
        records = records.filter(city__iexact=city)
    output = []
    for row in records[:5000]:
        p = row.pollutants or {}
        pm25, pm10 = p.get("pm25"), p.get("pm10")
        reasons = []
        pm25_time = _pollutant_time(row, "pm25")
        pm10_time = _pollutant_time(row, "pm10")
        if isinstance(pm25, (int, float)) and isfinite(pm25) and pm25 >= 60 and pm25_time and pm25_time >= since:
            reasons.append(f"PM2.5 {pm25:.1f} µg/m³")
        if isinstance(pm10, (int, float)) and isfinite(pm10) and pm10 >= 100 and pm10_time and pm10_time >= since:
            reasons.append(f"PM10 {pm10:.1f} µg/m³")
        if reasons:
            output.append({"station": row.station_name, "city": row.city, "state": row.state,
                "latitude": row.latitude, "longitude": row.longitude, "source": row.source,
                "observed_at": row.observed_at.isoformat(),
                "pollutant_times": row.pollutant_times or {},
                "reason": " · ".join(reasons), "kind": "threshold_flag"})
    return JsonResponse({"hotspots": output, "count": len(output),
        "note": "Rule-based screening flags (PM2.5 ≥60 or PM10 ≥100 µg/m³) from recent stored station readings. These are not verified incidents, official hotspot declarations or causal diagnoses."})


@require_GET
def health_advice(request):
    try:
        raw_aqi = request.GET.get("aqi")
        if raw_aqi is None:
            raise ValueError
        aqi = int(raw_aqi)
        if aqi < 0 or aqi > 500:
            raise ValueError
    except ValueError:
        return _error("Provide an AQI number between 0 and 500.")
    if aqi <= 50:
        level, advice = "Good", ["Usual outdoor activities are generally reasonable.", "Continue checking local updates as conditions can change."]
    elif aqi <= 100:
        level, advice = "Satisfactory", ["Most people can continue normal activities.", "Sensitive people should watch for symptoms and reduce prolonged exertion if uncomfortable."]
    elif aqi <= 200:
        level, advice = "Moderate", ["People with asthma or other respiratory sensitivity should limit prolonged outdoor exertion.", "Consider lower-intensity activity and take breaks indoors."]
    elif aqi <= 300:
        level, advice = "Poor", ["Reduce prolonged or heavy outdoor exertion.", "Sensitive groups should avoid strenuous outdoor activity and follow clinician advice."]
    elif aqi <= 400:
        level, advice = "Very Poor", ["Avoid strenuous outdoor activity; keep windows closed when outdoor air is worse.", "Use a well-fitted particulate respirator outdoors if exposure cannot be avoided."]
    else:
        level, advice = "Severe", ["Avoid outdoor physical activity where possible.", "Follow official local health advisories and seek medical help for serious symptoms."]
    return JsonResponse({"aqi": aqi, "category": level, "advice": advice,
        "note": "General educational guidance only. The AQI may be model-derived; this is not medical advice. Follow official CPCB/local health advisories."})


@require_GET
def route_compare(request):
    start_name, end_name = request.GET.get("start", "").strip(), request.GET.get("end", "").strip()
    if not start_name or not end_name:
        return _error("Provide both start and destination city names.")
    try:
        start, end = resolve_city(start_name), resolve_city(end_name)
        url = (f"https://router.project-osrm.org/route/v1/driving/"
               f"{start['longitude']},{start['latitude']};{end['longitude']},{end['latitude']}")
        response = requests.get(url, params={"overview": "full", "geometries": "geojson", "steps": "false", "alternatives": "true"}, timeout=25)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("code") != "Ok" or not payload.get("routes"):
            return _error("A route could not be found for these locations.", 502)
        recent = StationObservation.objects.filter(observed_at__gte=timezone.now()-timedelta(hours=48)).exclude(latitude__isnull=True).exclude(longitude__isnull=True)
        station_rows = list(recent.order_by("source", "station_id", "-observed_at").distinct("source", "station_id"))
        options = []
        for route_index, route in enumerate(payload["routes"][:3]):
            coordinates = route["geometry"]["coordinates"]
            step = max(1, len(coordinates) // 30)
            samples, used = [], set()
            for lon, lat in coordinates[::step][:30]:
                nearest, nearest_distance = None, 1e9
                for row in station_rows:
                    d = haversine_km(lat, lon, row.latitude, row.longitude)
                    value = (row.pollutants or {}).get("pm25")
                    pm25_time = _pollutant_time(row, "pm25")
                    if (isinstance(value, (int, float)) and isfinite(value) and value >= 0
                            and pm25_time and pm25_time >= timezone.now() - timedelta(hours=48)
                            and d < nearest_distance):
                        nearest, nearest_distance = row, d
                if nearest and nearest_distance <= 20 and (nearest.source, nearest.station_id) not in used:
                    used.add((nearest.source, nearest.station_id))
                    value = (nearest.pollutants or {}).get("pm25")
                    if isinstance(value, (int, float)):
                        samples.append({"station": nearest.station_name, "city": nearest.city,
                            "latitude": nearest.latitude, "longitude": nearest.longitude,
                            "distance_km": round(nearest_distance, 1), "pm25": round(value, 1),
                            "observed_at": _pollutant_time(nearest, "pm25").isoformat()})
            average = round(sum(x["pm25"] for x in samples)/len(samples), 1) if samples else None
            options.append({"route_number": route_index + 1, "distance_km": round(route["distance"]/1000, 1),
                "duration_minutes": round(route["duration"]/60), "geometry": coordinates,
                "sampled_stations": samples, "average_nearby_pm25": average})
        with_measurements = [item for item in options if item["average_nearby_pm25"] is not None]
        chosen = min(with_measurements, key=lambda item: item["average_nearby_pm25"]) if with_measurements else min(options, key=lambda item: item["duration_minutes"])
        return JsonResponse({"start": start, "end": end, "chosen_route": chosen,
            "routes": options, "selection_method": "lowest average nearby PM2.5" if with_measurements else "shortest travel time; no suitable nearby PM2.5 readings",
            "note": "AtmoIQ compares up to three road alternatives when the routing provider supplies them. Route scores average recent stored station PM2.5 values within 20 km of sampled route points. This is a coarse screening estimate, not continuous roadside measurement or a guarantee of lower personal exposure."})
    except (ValueError, requests.RequestException, KeyError, IndexError, TypeError) as exc:
        return _error(str(exc) or "Could not calculate this route.", 400 if isinstance(exc, ValueError) else 502)

@require_GET
def pollution_report(request):
    """Create a concise downloadable PDF snapshot for a selected city."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    city_name = request.GET.get("city", "").strip()[:100]
    if not city_name:
        return _error("Choose a city before downloading a report.")
    try:
        city = resolve_city(city_name)
        hourly = fetch_hourly(city)
        index = current_hour_index(hourly)
        pollutants = pollutants_at(hourly, index)
        modelled_at = local_time_from_provider(hourly["time"][index])
        prediction = predict_many([pollutants])[0] if has_prediction_coverage(pollutants) and settings.ML_ARTIFACT_PATH.exists() else None
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        y = height - 58
        pdf.setTitle(f"AtmoIQ air quality report - {city['name']}")
        pdf.setFont("Helvetica-Bold", 20); pdf.drawString(48, y, "AtmoIQ Pollution Report"); y -= 30
        pdf.setFont("Helvetica", 11); pdf.drawString(48, y, "City: " + ", ".join(part for part in (city["name"], city.get("state", "")) if part)); y -= 18
        pdf.drawString(48, y, f"Generated: {timezone.localtime():%d %b %Y, %I:%M %p %Z}"); y -= 18
        pdf.drawString(48, y, f"CAMS model hour: {modelled_at:%d %b %Y, %I:%M %p %Z}"); y -= 28
        pdf.setFont("Helvetica-Bold", 13); pdf.drawString(48, y, "Modelled pollutant snapshot"); y -= 22
        pdf.setFont("Helvetica", 11)
        for key in ("pm25", "pm10", "no2", "so2", "co", "o3", "nh3"):
            value = pollutants.get(key)
            unavailable_note = "Not supplied by CAMS Global" if key == "nh3" else "Not available"
            pdf.drawString(58, y, f"{key.upper()}: {value if value is not None else unavailable_note}")
            y -= 17
        y -= 8; pdf.setFont("Helvetica-Bold", 13); pdf.drawString(48, y, "AtmoIQ AQI estimate"); y -= 22
        pdf.setFont("Helvetica", 11)
        pdf.drawString(58, y, f"AQI: {prediction['aqi']} ({prediction['category']})" if prediction else "Not available - insufficient inputs or model not trained")
        y -= 24
        pdf.setFont("Helvetica-Bold", 11); pdf.drawString(48, y, "Source and interpretation"); y -= 18
        pdf.setFont("Helvetica", 9)
        for line in ["Source: Open-Meteo CAMS modelled atmospheric concentrations.",
                     "The displayed AQI is an AtmoIQ ML estimate, not an official CPCB station AQI.",
                     "This report is an informational snapshot, not medical advice or an official alert.",
                     "For verified monitoring, consult CPCB and local public-health advisories."]:
            pdf.drawString(48, y, line); y -= 15
        pdf.showPage(); pdf.save(); buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", city["name"]).strip("_") or "city"
        response["Content-Disposition"] = f'attachment; filename="AtmoIQ_{safe_name}_report.pdf"'
        return response
    except ValueError as exc:
        return _error(str(exc), 400)
    except (requests.RequestException, RuntimeError) as exc:
        return _error(str(exc), 502)
