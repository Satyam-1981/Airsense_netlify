from django.contrib import admin
from .models import ExposureRecord, ForecastSnapshot, HotspotReport, MonitoringStation, StationObservation


@admin.register(HotspotReport)
class HotspotReportAdmin(admin.ModelAdmin):
    list_display = ("category", "city", "observed_at", "status", "created_at")
    list_filter = ("status", "category", "city")
    search_fields = ("city", "description")
    readonly_fields = ("created_at",)


@admin.register(StationObservation)
class StationObservationAdmin(admin.ModelAdmin):
    list_display = ("station_name", "city", "state", "source", "observed_at")
    list_filter = ("source", "state")
    search_fields = ("station_name", "city", "state")


@admin.register(ForecastSnapshot)
class ForecastSnapshotAdmin(admin.ModelAdmin):
    list_display = ("city", "forecast_at", "predicted_aqi", "model_version")
    list_filter = ("city",)


@admin.register(ExposureRecord)
class ExposureRecordAdmin(admin.ModelAdmin):
    list_display = ("city", "activity", "duration_minutes", "aqi", "recorded_at")
    list_filter = ("activity", "city")


@admin.register(MonitoringStation)
class MonitoringStationAdmin(admin.ModelAdmin):
    list_display = ("station_name", "city", "state", "source", "last_seen_at")
    list_filter = ("source", "state")
    search_fields = ("station_name", "city", "state")
