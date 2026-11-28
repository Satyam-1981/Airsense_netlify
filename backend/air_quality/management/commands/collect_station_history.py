from django.core.management.base import BaseCommand
from django.db import transaction
import requests

from air_quality.models import MonitoringStation, StationObservation
from air_quality.providers import get_cpcb_stations, get_openaq_stations, resolve_city

DEFAULT_CITIES = ["Kolkata", "Delhi", "Mumbai", "Bengaluru", "Chennai", "Hyderabad", "Dhanbad"]


class Command(BaseCommand):
    help = "Fetch current CPCB/OpenAQ station readings and store observations for historical trends."

    def add_arguments(self, parser):
        parser.add_argument("--cities", default=",".join(DEFAULT_CITIES), help="Comma-separated Indian city names.")

    def handle(self, *args, **options):
        cities = [name.strip() for name in options["cities"].split(",") if name.strip()]
        saved = 0
        for name in cities:
            try:
                city = resolve_city(name)
            except (ValueError, requests.RequestException) as exc:
                self.stderr.write(self.style.WARNING(f"{name}: city lookup skipped ({exc})"))
                continue
            stations = []
            try:
                stations.extend(get_cpcb_stations(city=city["name"]))
            except requests.RequestException as exc:
                self.stderr.write(self.style.WARNING(f"{name}: CPCB lookup failed ({exc})"))
            try:
                stations.extend(get_openaq_stations(city["latitude"], city["longitude"], city["name"], city.get("state", "")))
            except requests.RequestException as exc:
                self.stderr.write(self.style.WARNING(f"{name}: OpenAQ lookup failed ({exc})"))
            if not stations:
                self.stderr.write(self.style.WARNING(f"{city['name']}: no station readings returned. Check provider keys and availability; no synthetic readings were added."))
                continue
            with transaction.atomic():
                for station in stations:
                    MonitoringStation.objects.update_or_create(
                        source=station["source"], station_id=station["station_id"],
                        defaults={"station_name": station["name"], "city": station.get("city", ""),
                                  "state": station.get("state", ""), "latitude": station.get("latitude"),
                                  "longitude": station.get("longitude")},
                    )
                    if station.get("observed_at") is None:
                        continue
                    StationObservation.objects.update_or_create(
                        source=station["source"], station_id=station["station_id"], observed_at=station.get("observed_at"),
                        defaults={
                            "station_name": station["name"], "city": station.get("city", ""),
                            "state": station.get("state", ""), "latitude": station.get("latitude"),
                            "longitude": station.get("longitude"), "pollutants": station.get("pollutants", {}),
                            "pollutant_times": station.get("pollutant_times", {}),
                        },
                    )
                    saved += 1
            self.stdout.write(f"{city['name']}: checked {len(stations)} monitoring stations")
        if saved:
            self.stdout.write(self.style.SUCCESS(f"Station history collection complete: {saved} timestamped station snapshots saved or refreshed."))
        else:
            self.stderr.write(self.style.WARNING("No timestamped station observations were saved. Check API keys, provider access and network availability."))
