from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from air_quality.models import MonitoringStation, StationObservation
from air_quality.providers import get_cpcb_stations


class Command(BaseCommand):
    help = "Refresh the nationwide CPCB station directory/readings and store timestamped observations."

    def handle(self, *args, **options):
        if not settings.DATA_GOV_IN_API_KEY:
            raise CommandError("DATA_GOV_IN_API_KEY is missing. Add a valid data.gov.in key to .env before refreshing the CPCB network.")
        try:
            stations = get_cpcb_stations()
        except Exception as exc:
            raise CommandError(f"CPCB/data.gov.in refresh failed: {exc}") from exc

        if not stations:
            raise CommandError("The CPCB/data.gov.in resource returned no station records. Check the API key, resource access, quota and network. No records were fabricated.")

        saved_observations = 0
        with transaction.atomic():
            for station in stations:
                observed_at = station.get("observed_at")
                MonitoringStation.objects.update_or_create(
                    source=station["source"], station_id=station["station_id"],
                    defaults={"station_name": station["name"], "city": station.get("city", ""),
                              "state": station.get("state", ""), "latitude": station.get("latitude"),
                              "longitude": station.get("longitude")},
                )
                if observed_at is None:
                    continue
                StationObservation.objects.update_or_create(
                    source=station["source"], station_id=station["station_id"], observed_at=observed_at,
                    defaults={
                        "station_name": station["name"], "city": station.get("city", ""),
                        "state": station.get("state", ""), "latitude": station.get("latitude"),
                        "longitude": station.get("longitude"), "pollutants": station.get("pollutants", {}),
                        "pollutant_times": station.get("pollutant_times", {}),
                    },
                )
                saved_observations += 1

        self.stdout.write(self.style.SUCCESS(
            f"Refreshed {len(stations)} CPCB station directory entries; saved/updated {saved_observations} timestamped observations at {timezone.localtime():%Y-%m-%d %H:%M %Z}."
        ))
