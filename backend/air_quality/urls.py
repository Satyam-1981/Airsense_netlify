from django.urls import path
from . import views

urlpatterns = [
    path("csrf/", views.csrf_token, name="csrf-token"),
    path("health/", views.health, name="health"),
    path("city/", views.city_current, name="city-current"),
    path("forecast/", views.forecast, name="forecast"),
    path("stations/", views.stations, name="stations"),
    path("network/india/", views.india_network, name="india-network"),
    path("hotspots/detected/", views.detected_hotspots, name="detected-hotspots"),
    path("advice/", views.health_advice, name="health-advice"),
    path("route/", views.route_compare, name="route-compare"),
    path("reports/pdf/", views.pollution_report, name="pollution-report-pdf"),
    path("predict/", views.predict, name="predict"),
    path("sensitivity/", views.sensitivity_analysis, name="sensitivity"),
    path("ml/metrics/", views.ml_metrics, name="ml-metrics"),
    path("history/", views.history, name="history"),
    path("anomalies/", views.anomalies, name="anomalies"),
    path("hotspots/", views.hotspots, name="hotspots"),
    path("exposure/", views.exposure, name="exposure"),
]
