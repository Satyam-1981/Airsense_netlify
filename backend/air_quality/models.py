import uuid
from django.db import models


class StationObservation(models.Model):
    source = models.CharField(max_length=32)
    station_id = models.CharField(max_length=220)
    station_name = models.CharField(max_length=240)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    observed_at = models.DateTimeField(null=True, blank=True)
    pollutants = models.JSONField(default=dict)
    pollutant_times = models.JSONField(default=dict, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)
    fetched_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["source", "station_id", "observed_at"], name="unique_station_observation")]
        indexes = [models.Index(fields=["city", "observed_at"], name="air_quality_city_5f8bf2_idx"), models.Index(fields=["station_id", "observed_at"], name="air_quality_statio_8a5d01_idx")]
        ordering = ["-observed_at"]


class ForecastSnapshot(models.Model):
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    forecast_at = models.DateTimeField()
    generated_at = models.DateTimeField(auto_now_add=True)
    predicted_aqi = models.PositiveSmallIntegerField()
    category = models.CharField(max_length=32)
    pollutants = models.JSONField(default=dict)
    model_version = models.CharField(max_length=100, blank=True)
    source = models.CharField(max_length=160, default="Open-Meteo CAMS modelled concentrations")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["city", "forecast_at", "model_version"], name="unique_city_forecast_model")]
        indexes = [models.Index(fields=["city", "forecast_at"], name="air_quality_city_f2e12a_idx"), models.Index(fields=["generated_at"], name="air_quality_generat_7f231a_idx")]
        ordering = ["forecast_at"]


class HotspotReport(models.Model):
    class Category(models.TextChoices):
        SMOKE = "smoke", "Smoke"
        DUST = "dust", "Dust"
        OPEN_BURNING = "open_burning", "Open burning"
        INDUSTRIAL = "industrial", "Industrial emissions"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.CharField(max_length=24, choices=Category.choices)
    description = models.CharField(max_length=500, blank=True)
    city = models.CharField(max_length=100)
    latitude = models.FloatField()
    longitude = models.FloatField()
    observed_at = models.DateTimeField()
    photo = models.ImageField(upload_to="hotspots/%Y/%m/", null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["status", "created_at"], name="air_quality_status_3b10ef_idx"), models.Index(fields=["city", "observed_at"], name="air_quality_city_3e6e57_idx")]
        ordering = ["-created_at"]


class ExposureRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client_id = models.CharField(max_length=80, db_index=True)
    city = models.CharField(max_length=100)
    activity = models.CharField(max_length=32)
    duration_minutes = models.PositiveSmallIntegerField()
    aqi = models.PositiveSmallIntegerField(null=True, blank=True)
    pm25 = models.FloatField(null=True, blank=True)
    data_source = models.CharField(max_length=100, default="AtmoIQ modelled city estimate")
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["client_id", "recorded_at"], name="air_quality_client_9aa4ce_idx")]
        ordering = ["-recorded_at"]


class MonitoringStation(models.Model):
    """Latest known station directory entry, even when it has no reading yet."""
    source = models.CharField(max_length=32)
    station_id = models.CharField(max_length=220)
    station_name = models.CharField(max_length=240)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["source", "station_id"], name="unique_monitoring_station")]
        indexes = [models.Index(fields=["state", "city"], name="air_quality_station_area_idx")]
        ordering = ["state", "city", "station_name"]
