from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("air_quality", "0003_stationobservation_pollutant_times")]
    operations = [
        migrations.AddField(
            model_name="stationobservation",
            name="fetched_at",
            field=models.DateTimeField(auto_now=True, blank=True, null=True),
        ),
    ]
