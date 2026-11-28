import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="StationObservation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source", models.CharField(max_length=32)),
                ("station_id", models.CharField(max_length=220)),
                ("station_name", models.CharField(max_length=240)),
                ("city", models.CharField(blank=True, max_length=100)),
                ("state", models.CharField(blank=True, max_length=100)),
                ("latitude", models.FloatField(blank=True, null=True)),
                ("longitude", models.FloatField(blank=True, null=True)),
                ("observed_at", models.DateTimeField(blank=True, null=True)),
                ("pollutants", models.JSONField(default=dict)),
                ("recorded_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-observed_at"]},
        ),
        migrations.CreateModel(
            name="ForecastSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("city", models.CharField(max_length=100)),
                ("state", models.CharField(blank=True, max_length=100)),
                ("latitude", models.FloatField(blank=True, null=True)),
                ("longitude", models.FloatField(blank=True, null=True)),
                ("forecast_at", models.DateTimeField()),
                ("generated_at", models.DateTimeField(auto_now_add=True)),
                ("predicted_aqi", models.PositiveSmallIntegerField()),
                ("category", models.CharField(max_length=32)),
                ("pollutants", models.JSONField(default=dict)),
                ("model_version", models.CharField(blank=True, max_length=100)),
                ("source", models.CharField(default="Open-Meteo CAMS modelled concentrations", max_length=160)),
            ],
            options={"ordering": ["forecast_at"]},
        ),
        migrations.CreateModel(
            name="HotspotReport",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("category", models.CharField(choices=[("smoke", "Smoke"), ("dust", "Dust"), ("open_burning", "Open burning"), ("industrial", "Industrial emissions"), ("other", "Other")], max_length=24)),
                ("description", models.CharField(blank=True, max_length=500)),
                ("city", models.CharField(max_length=100)),
                ("latitude", models.FloatField()),
                ("longitude", models.FloatField()),
                ("observed_at", models.DateTimeField()),
                ("photo", models.ImageField(blank=True, null=True, upload_to="hotspots/%Y/%m/")),
                ("status", models.CharField(choices=[("pending", "Pending review"), ("verified", "Verified"), ("rejected", "Rejected")], default="pending", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="ExposureRecord",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("client_id", models.CharField(db_index=True, max_length=80)),
                ("city", models.CharField(max_length=100)),
                ("activity", models.CharField(max_length=32)),
                ("duration_minutes", models.PositiveSmallIntegerField()),
                ("aqi", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("pm25", models.FloatField(blank=True, null=True)),
                ("data_source", models.CharField(default="AtmoIQ modelled city estimate", max_length=100)),
                ("recorded_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-recorded_at"]},
        ),
        migrations.AddConstraint(
            model_name="stationobservation",
            constraint=models.UniqueConstraint(fields=("source", "station_id", "observed_at"), name="unique_station_observation"),
        ),
        migrations.AddConstraint(
            model_name="forecastsnapshot",
            constraint=models.UniqueConstraint(fields=("city", "forecast_at", "model_version"), name="unique_city_forecast_model"),
        ),
        migrations.AddIndex(model_name="stationobservation", index=models.Index(fields=["city", "observed_at"], name="air_quality_city_5f8bf2_idx")),
        migrations.AddIndex(model_name="stationobservation", index=models.Index(fields=["station_id", "observed_at"], name="air_quality_statio_8a5d01_idx")),
        migrations.AddIndex(model_name="forecastsnapshot", index=models.Index(fields=["city", "forecast_at"], name="air_quality_city_f2e12a_idx")),
        migrations.AddIndex(model_name="forecastsnapshot", index=models.Index(fields=["generated_at"], name="air_quality_generat_7f231a_idx")),
        migrations.AddIndex(model_name="hotspotreport", index=models.Index(fields=["status", "created_at"], name="air_quality_status_3b10ef_idx")),
        migrations.AddIndex(model_name="hotspotreport", index=models.Index(fields=["city", "observed_at"], name="air_quality_city_3e6e57_idx")),
        migrations.AddIndex(model_name="exposurerecord", index=models.Index(fields=["client_id", "recorded_at"], name="air_quality_client_9aa4ce_idx")),
    ]
