from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, Client, override_settings
from django.utils import timezone

from ml.predictor import category, has_prediction_coverage
from .models import ExposureRecord, HotspotReport, MonitoringStation, StationObservation
from .providers import get_cpcb_stations, get_openaq_stations, native_cams_points, normalize_concentration, pollutants_at


class UtilityTests(TestCase):
    def test_aqi_categories(self):
        self.assertEqual(category(0), "Good")
        self.assertEqual(category(50), "Good")
        self.assertEqual(category(100), "Satisfactory")
        self.assertEqual(category(200), "Moderate")
        self.assertEqual(category(300), "Poor")
        self.assertEqual(category(400), "Very Poor")
        self.assertEqual(category(500), "Severe")

    def test_prediction_requires_all_six_supported_inputs_without_imputation(self):
        complete = {"pm25": 20, "pm10": 40, "no2": 15, "so2": 5, "co": 0.4, "o3": 30}
        self.assertTrue(has_prediction_coverage(complete))
        self.assertFalse(has_prediction_coverage({**complete, "o3": None}))
        self.assertFalse(has_prediction_coverage({"no2": 15, "so2": 7, "co": 0.4, "o3": 10}))

    def test_unit_conversion_skips_ambiguous_units(self):
        self.assertEqual(normalize_concentration(2500, "µg/m³", "co"), 2.5)
        self.assertEqual(normalize_concentration(0.8, "mg/m3", "pm25"), 800)
        self.assertIsNone(normalize_concentration(0.4, "ppm", "no2"))

    def test_running_pollutant_average_requires_enough_values(self):
        hourly = {
            "pm2_5": [10] * 8, "pm10": [20] * 8,
            "nitrogen_dioxide": [5] * 8, "sulphur_dioxide": [2] * 8,
            "carbon_monoxide": [1000] * 8, "ozone": [30] * 8,
        }
        result = pollutants_at(hourly, 7)
        self.assertEqual(result["pm25"], 10)
        self.assertEqual(result["co"], 1)
        self.assertEqual(result["o3"], 30)
        self.assertIsNone(result["nh3"])
        self.assertIsNone(pollutants_at({"pm2_5": [10], "pm10": [20]}, 0)["pm25"])

    def test_native_cams_series_discards_interpolated_hourly_values_and_keeps_gaps(self):
        times = [f"2026-11-28T{hour:02d}:00" for hour in range(24)]
        native = native_cams_points({"time": times, "pm2_5": list(range(24))})
        self.assertEqual(len(native["time"]), 8)
        self.assertEqual(native["pm2_5"], [0, 3, 6, 9, 12, 15, 18, 21])

        gapped_times = ["2026-11-28T00:00", "2026-11-28T03:00", "2026-11-28T06:00",
                        "2026-11-28T12:00", "2026-11-28T15:00", "2026-11-28T18:00", "2026-11-28T21:00"]
        gapped = native_cams_points({"time": gapped_times, "pm2_5": [10, 20, 30, 40, 50, 60, 70]})
        self.assertEqual(len(gapped["time"]), 8)
        self.assertIsNone(gapped["pm2_5"][3])


class ApiTests(TestCase):
    def test_health_endpoint(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("database", response.json())

    def test_anonymous_exposure_can_be_saved_read_and_deleted(self):
        client_id = "test-browser-client-identifier"
        response = self.client.post("/api/exposure/", data={
            "client_id": client_id, "city": "Kolkata", "activity": "walking",
            "duration_minutes": 35, "aqi": 92, "pm25": 35.2,
        }, content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ExposureRecord.objects.count(), 1)
        listed = self.client.get("/api/exposure/", {"client_id": client_id})
        self.assertEqual(len(listed.json()["records"]), 1)
        deleted = self.client.delete(f"/api/exposure/?client_id={client_id}")
        self.assertEqual(deleted.json()["deleted"], 1)

    def test_exposure_rejects_unreasonable_duration(self):
        response = self.client.post("/api/exposure/", data={
            "client_id": "test-browser-client-identifier", "city": "Kolkata",
            "activity": "walking", "duration_minutes": 900,
        }, content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_hotspot_report_is_unverified_until_reviewed(self):
        observed_at = timezone.now().isoformat()
        response = self.client.post("/api/hotspots/", data={
            "category": "smoke", "city": "Kolkata", "latitude": "22.57",
            "longitude": "88.36", "observed_at": observed_at,
            "description": "Visible smoke near the road.",
        })
        self.assertEqual(response.status_code, 201)
        report = HotspotReport.objects.get()
        self.assertEqual(report.status, HotspotReport.Status.PENDING)
        public = self.client.get("/api/hotspots/")
        self.assertEqual(public.json()["reports"][0]["status_label"], "Unverified community report")

    def test_anomaly_detection_needs_history_and_flags_large_spike(self):
        now = timezone.now()
        for index in range(10):
            StationObservation.objects.create(
                source="OpenAQ", station_id="station-1", station_name="Test station", city="Kolkata",
                observed_at=now - timedelta(hours=10 - index), pollutants={"pm25": 12.0},
            )
        StationObservation.objects.create(
            source="OpenAQ", station_id="station-1", station_name="Test station", city="Kolkata",
            observed_at=now, pollutants={"pm25": 65.0},
        )
        response = self.client.get("/api/anomalies/", {"city": "Kolkata"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["anomalies"]), 1)
        self.assertEqual(response.json()["anomalies"][0]["pollutant"], "pm25")

    def test_exposure_rejects_non_finite_pollution_values(self):
        response = self.client.post("/api/exposure/", data={
            "client_id": "test-browser-client-identifier", "city": "Kolkata",
            "activity": "walking", "duration_minutes": 30, "aqi": float("nan"),
        }, content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_sensitivity_endpoint_rejects_non_object_payload(self):
        response = self.client.post("/api/sensitivity/", data="[]", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_prediction_endpoint_rejects_insufficient_pollutants(self):
        response = self.client.post("/api/predict/", data={
            "pollutants": {"pm25": 22, "no2": 12},
        }, content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_prediction_endpoint_rejects_invalid_optional_pollutant(self):
        response = self.client.post("/api/predict/", data={
            "pollutants": {"pm25": 22, "pm10": 35, "no2": 12, "so2": "not-a-number"},
        }, content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_prediction_endpoint_does_not_accept_nh3_as_a_cams_global_feature(self):
        response = self.client.post("/api/predict/", data={
            "pollutants": {"pm25": 22, "pm10": 35, "no2": 12, "so2": 5, "co": 0.4, "o3": 30, "nh3": 8},
        }, content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_history_keeps_different_stations_separate(self):
        now = timezone.now()
        for station_id, station_name, value, offset in [
            ("station-a", "Station A", 12.0, 0),
            ("station-b", "Station B", 35.0, 1),
        ]:
            StationObservation.objects.create(
                source="OpenAQ", station_id=station_id, station_name=station_name,
                city="Kolkata", observed_at=now - timedelta(hours=offset),
                pollutants={"pm25": value},
            )
        response = self.client.get("/api/history/", {"city": "Kolkata", "days": 30})
        series = [row for row in response.json()["series"] if row["pollutant"] == "pm25"]
        self.assertEqual(len(series), 2)
        self.assertEqual({row["station_id"] for row in series}, {"station-a", "station-b"})


    def test_anomaly_history_deduplicates_carried_forward_pollutant_timestamps(self):
        now = timezone.now()
        same_pollutant_time = now - timedelta(minutes=20)
        for index in range(12):
            StationObservation.objects.create(
                source="OpenAQ", station_id="same-sensor-time", station_name="Same sensor time", city="Kolkata",
                observed_at=now - timedelta(minutes=12 - index),
                pollutants={"pm25": 12.0},
                pollutant_times={"pm25": same_pollutant_time.isoformat()},
            )
        response = self.client.get("/api/anomalies/", {"city": "Kolkata"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["anomalies"], [])

    def test_history_counts_unique_pollutant_measurement_times(self):
        now = timezone.now()
        measurement_time = now - timedelta(minutes=20)
        for index in range(3):
            StationObservation.objects.create(
                source="OpenAQ", station_id="same-history-sensor", station_name="Same history sensor", city="Kolkata",
                observed_at=now - timedelta(minutes=10 - index), pollutants={"pm25": 20.0},
                pollutant_times={"pm25": measurement_time.isoformat()},
            )
        response = self.client.get("/api/history/", {"city": "Kolkata", "days": 30})
        series = [row for row in response.json()["series"] if row["station_id"] == "same-history-sensor" and row["pollutant"] == "pm25"]
        self.assertEqual(len(series), 1)
        self.assertEqual(series[0]["samples"], 1)

    def test_anomaly_detection_ignores_stale_latest_measurement(self):
        now = timezone.now()
        for index in range(10):
            StationObservation.objects.create(
                source="OpenAQ", station_id="stale-station", station_name="Stale station", city="Kolkata",
                observed_at=now - timedelta(hours=100 - index), pollutants={"pm25": 12.0},
            )
        StationObservation.objects.create(
            source="OpenAQ", station_id="stale-station", station_name="Stale station", city="Kolkata",
            observed_at=now - timedelta(hours=80), pollutants={"pm25": 65.0},
        )
        response = self.client.get("/api/anomalies/", {"city": "Kolkata"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["anomalies"], [])


class OpenAQProviderTests(TestCase):
    @override_settings(OPENAQ_API_KEY="test-key")
    @patch("air_quality.providers._get_json")
    def test_latest_readings_are_joined_to_sensor_metadata(self, get_json):
        get_json.side_effect = [
            {"results": [{"id": 123, "name": "Test monitor", "locality": "Kolkata", "coordinates": {"latitude": 22.57, "longitude": 88.36}}]},
            {"results": [
                {"id": 11, "parameter": {"name": "pm25", "units": "µg/m³"}},
                {"id": 12, "parameter": {"name": "no2", "units": "µg/m³"}},
            ]},
            {"results": [
                {"sensorsId": 11, "value": 19.0, "datetime": {"utc": "2026-11-28T04:00:00Z"}},
                {"sensorsId": 11, "value": 24.5, "datetime": {"utc": "2026-11-28T05:00:00Z"}},
                {"sensorsId": 12, "value": 18.0, "datetime": {"utc": "2026-11-28T04:30:00Z"}},
                {"sensorsId": 999, "value": 600, "datetime": {"utc": "2026-11-28T05:00:00Z"}},
            ]},
        ]
        stations = get_openaq_stations(22.57, 88.36, "Kolkata", "West Bengal")
        self.assertEqual(len(stations), 1)
        self.assertEqual(stations[0]["pollutants"], {"pm25": 24.5, "no2": 18.0})
        self.assertEqual(stations[0]["pollutant_times"]["pm25"], "2026-11-28T05:00:00+00:00")
        self.assertEqual(stations[0]["pollutant_times"]["no2"], "2026-11-28T04:30:00+00:00")
        self.assertEqual(stations[0]["name"], "Test monitor")


class CPCBProviderTests(TestCase):
    @override_settings(DATA_GOV_IN_API_KEY="test-key")
    @patch("air_quality.providers._get_json")
    def test_station_records_keep_latest_value_and_pollutant_timestamp(self, get_json):
        base = {
            "state": "Jharkhand", "city": "Dhanbad", "station": "Test monitoring station",
            "latitude": "23.79", "longitude": "86.43", "pollutant_id": "PM2.5",
            "pollutant_unit": "µg/m³",
        }
        get_json.return_value = {"records": [
            {**base, "pollutant_avg": "42", "last_update": "2026-11-28T09:00:00"},
            {**base, "pollutant_avg": "35", "last_update": "2026-11-28T10:00:00"},
        ]}
        stations = get_cpcb_stations()
        self.assertEqual(len(stations), 1)
        self.assertEqual(stations[0]["pollutants"]["pm25"], 35.0)
        self.assertEqual(stations[0]["pollutant_times"]["pm25"], "2026-11-28T10:00:00+05:30")


class CsrfTests(TestCase):
    def test_write_endpoints_require_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post("/api/exposure/", data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 403)
        token_response = client.get("/api/csrf/")
        self.assertEqual(token_response.status_code, 200)
        token = client.cookies["csrftoken"].value
        response = client.post("/api/exposure/", data="{}", content_type="application/json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 400)


class NetworkAndAdviceTests(TestCase):
    def test_nationwide_station_map_includes_directory_entries_without_readings(self):
        MonitoringStation.objects.create(source="CPCB", station_id="new-station", station_name="New station",
            city="Dhanbad", state="Jharkhand", latitude=23.79, longitude=86.43)
        response = self.client.get("/api/network/india/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertIsNone(response.json()["stations"][0]["observed_at"])

    def test_hotspot_screening_uses_recent_station_thresholds(self):
        StationObservation.objects.create(source="CPCB", station_id="pm25-high", station_name="High PM station",
            city="Dhanbad", latitude=23.79, longitude=86.43, observed_at=timezone.now(), pollutants={"pm25": 72.0})
        response = self.client.get("/api/hotspots/detected/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertIn("PM2.5", response.json()["hotspots"][0]["reason"])

    def test_health_advice_endpoint_returns_category_and_caveat(self):
        response = self.client.get("/api/advice/", {"aqi": 250})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["category"], "Poor")
        self.assertIn("not medical advice", response.json()["note"])

    def test_health_advice_requires_a_real_aqi_input_in_supported_range(self):
        self.assertEqual(self.client.get("/api/advice/").status_code, 400)
        self.assertEqual(self.client.get("/api/advice/", {"aqi": 501}).status_code, 400)

