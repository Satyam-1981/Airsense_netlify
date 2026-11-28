from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("air_quality", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="MonitoringStation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source", models.CharField(max_length=32)),
                ("station_id", models.CharField(max_length=220)),
                ("station_name", models.CharField(max_length=240)),
                ("city", models.CharField(blank=True, max_length=100)),
                ("state", models.CharField(blank=True, max_length=100)),
                ("latitude", models.FloatField(blank=True, null=True)),
                ("longitude", models.FloatField(blank=True, null=True)),
                ("last_seen_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["state", "city", "station_name"]},
        ),
        migrations.AddConstraint(
            model_name="monitoringstation",
            constraint=models.UniqueConstraint(fields=("source", "station_id"), name="unique_monitoring_station"),
        ),
        migrations.AddIndex(
            model_name="monitoringstation",
            index=models.Index(fields=["state", "city"], name="air_quality_station_area_idx"),
        ),
    ]
