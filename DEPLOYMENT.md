# Deployment notes

AtmoIQ does not select a hosting provider. Choose a platform that can run a React static build, a Django/Python application, PostgreSQL and media uploads.

## Runtime requirements

- Python 3.11 or newer (use a Python version supported by the installed scikit-learn release).
- Node.js 22.12+ and npm 10.9+ for the frontend build.
- PostgreSQL 14+.
- Persistent media storage for user-submitted hotspot photographs.
- Persistent storage for generated ML artifacts (`ml/artifacts/AtmoIQ_models.joblib` and `metrics.json`).

## Application settings

Set environment variables from `.env.example` in the selected hosting environment. In production:

- Set `DJANGO_DEBUG=false`.
- Use a strong private `DJANGO_SECRET_KEY`.
- Set `DJANGO_ALLOWED_HOSTS` to the real backend host names.
- Set `DATABASE_URL` to PostgreSQL.
- Configure station API keys if station data is required.
- Build and provide the trained ML artifacts to the Django process.
- Persist the Django media directory or use an equivalent object-storage integration.
- Serve the React build and route `/api/` and `/media/` to Django under the same site origin, or configure a deliberate production CORS/CSRF policy if they must be separate origins.

## Basic release checks

```bash
python backend/manage.py check --deploy
python backend/manage.py migrate
python backend/manage.py collectstatic --noinput
cd frontend && npm install && npm run build
```

Create a Django superuser if administrators will moderate hotspot reports. Arrange scheduled jobs for `python backend/manage.py refresh_station_network` (for nationwide CPCB station-directory refresh; e.g. hourly) and `python backend/manage.py collect_station_history --cities Kolkata,Dhanbad,Delhi,Mumbai` (for repeated historical snapshots in selected cities). Run them with Windows Task Scheduler, cron or the host's scheduler. The React map polls the stored directory every 60 seconds; dashboard/forecast and nearby-station views refresh around every five minutes; this is UI refresh only and does not change external provider publication times.

The route comparison requires outbound access to the public OSRM routing endpoint. PDF generation uses ReportLab, included in `requirements.txt`. The nationwide directory sync requires the configured CPCB/data.gov.in API key and resource access. OpenAQ records are discovered on city station searches rather than through a full national crawl.

No provider-specific deploy manifests or hosting adapters are included. Database backups and uploaded image backups should be part of the chosen platform's operational process.
