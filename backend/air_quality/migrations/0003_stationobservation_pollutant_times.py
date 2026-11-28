from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("air_quality", "0002_monitoringstation")]
    operations = [
        migrations.AddField(
            model_name="stationobservation",
            name="pollutant_times",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
