# AtmoIQ

**AtmoIQ is an India-focused air-quality companion.** It combines available monitoring-station observations, modelled atmospheric data, short-term forecasts and a small, transparent ML ensemble to help people understand local air quality and make better day-to-day decisions.

The project uses the stack requested for this build:

- **Frontend:** React, JavaScript, HTML and CSS, built with Vite; Recharts for charts and Leaflet with OpenStreetMap for maps.
- **Backend:** Python and Django (JSON API; no separate Node server).
- **Database:** PostgreSQL.
- **Machine learning:** pandas, NumPy and scikit-learn.

There is no FastAPI service, SQLite history database, Node server-side framework, Redis, Celery, Docker requirement or deployment-provider configuration.

## Features

### Phase 1 — Everyday air-quality features

- **City air-quality snapshot:** Indian city lookup, six CAMS Global modelled pollutant values, the AtmoIQ AQI proxy, source and modelled-hour timestamp. NH3 is shown only in station views/history when a station provider reports it.
- **Nearby monitoring stations:** CPCB/data.gov.in and OpenAQ station discovery, an interactive OpenStreetMap view, distance sorting, latest supported readings and timestamps. Browser location is optional and only requested when the user asks to use it.
- **All-India station map:** a nationwide directory map with station source, location, latest stored pollutants and separate directory, provider-observation and last-fetch timestamps. It is a view of the latest data AtmoIQ has retrieved, not a continuous live sensor feed. CPCB directory refresh can discover new stations; city lookups also add discovered OpenAQ stations. For OpenAQ, each pollutant retains its own source timestamp because sensors can update at different times.
- **Scheduled station refresh:** `refresh_station_network` updates the nationwide CPCB directory and observations when the configured data.gov.in resource is accessible. The browser map checks the database every 60 seconds; city and nearby-station screens refresh about every five minutes. The map refresh is database polling only. Provider publication cadence, API quotas, key validity and network availability control when new measurements exist; no freshness is promised when the provider is delayed or unavailable.
- **Requested AQI forecast horizons:** 3, 6 and 24-hour AQI proxy estimates when a valid native CAMS point is available. The 1-hour card explicitly reports unavailable because CAMS Global is native 3-hourly; AtmoIQ does not interpolate to invent a 1-hour prediction.
- **Pollution hotspot screening:** recent station records are flagged when PM2.5 is at least 60 µg/m³ or PM10 is at least 100 µg/m³. These are explainable threshold flags, not verified incidents or causal findings.
- **Forecast:** up to five days of native 3-hour provider points, ensemble AQI-proxy estimates and the lowest available forecast point in the next 24 hours. AtmoIQ does not use interpolated hourly values.
- **Smart alerts:** user-set AQI threshold, optional large-rise alert, quiet mode and browser notifications. The page must remain open and refresh data; alerts compare each selected city only with that city’s previous update. This is not background push or an official alert service.
- **Health guidance:** plain-language precautions for general users and more sensitive groups, with AQI-category guidance and limitations.
- **Comparative route screening:** requests up to three driving alternatives from the public OSRM routing service and ranks available options by average recent PM2.5 readings from nearby stored stations. Only PM2.5 values with their own timestamp no older than 48 hours are considered. If no suitable readings exist, it falls back to the shortest travel time and clearly says no pollution comparison was available. It is not a guaranteed cleanest route.
- **PDF pollution report:** downloads a selected-city snapshot containing modelled pollutant estimates, the AtmoIQ AQI proxy, the modelled data hour, generation time and source caveats. A city must be explicitly selected; the report does not silently substitute an example city.

### Phase 2 — Useful personal and analytical features

- **Favourite cities and comparison:** up to five favourites saved in browser storage; current values are compared using the same city endpoint.
- **Historical trends:** daily pollutant averages from station readings AtmoIQ has actually stored. Each station and provider remains separate so readings from different locations are not silently blended.
- **Pollution anomaly detection:** robust median/MAD comparison against each station's own history. At least ten earlier readings are required, and the latest reading must be no older than 72 hours. A statistical flag is not proof of an incident or its cause.
- **Prediction reliability indicators:** ensemble disagreement, input completeness and held-out test error. These are not calibrated confidence probabilities or validated official AQI accuracy.

### Phase 3 — Community and personal utilities

- **Pollution hotspot reports:** users can report visible smoke, dust, open burning or industrial emissions with location, observation time and an optional image. Reports appear on an OpenStreetMap view, are labelled as unverified and remain so until reviewed in Django Admin.
- **Personal activity/exposure history:** an account-free activity log stores duration and area-level readings against a random browser ID. Users can delete linked records; the browser ID is not an authenticated account or secure identity check. It is not a personal dosimeter or medical exposure assessment.

## Project structure

```text
AtmoIQ/
├── backend/
│   ├── config/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── asgi.py
│   │   └── wsgi.py
│   ├── air_quality/
│   │   ├── migrations/
│   │   ├── management/commands/
│   │   │   ├── collect_station_history.py
│   │   │   └── refresh_station_network.py
│   │   ├── models.py
│   │   ├── providers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── admin.py
│   │   └── tests.py
│   └── manage.py
├── ml/
│   ├── artifacts/             # generated locally; not committed
│   ├── predictor.py
│   └── train.py
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   └── MapView.jsx
│   │   ├── pages/              # includes IndiaMap.jsx and RouteFinder.jsx
│   │   ├── api.js
│   │   ├── utils.js
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── styles.css
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── .env.example
├── .gitignore
├── requirements.txt
├── DATA_SOURCES.md
├── DEPLOYMENT.md
└── README.md
```

The code is grouped by responsibility: React pages and reusable components, Django provider/API/model code, and a single ML training/inference area. A small `MonitoringStation` table stores the known station directory independently from `StationObservation`, so a station can appear on the map before its first valid timestamped reading. `StationObservation.pollutant_times` retains per-pollutant timestamps where providers supply different update times; older records without these timestamps use the station-level timestamp and are labelled accordingly. TanStack, TypeScript, FastAPI, SQLite, duplicate ingestion scripts and old deployment manifests have been removed.

## Local setup

### 1. Create PostgreSQL database

Create a database named `AtmoIQ` in your local PostgreSQL installation. For example, using `psql`:

```sql
CREATE DATABASE AtmoIQ;
```

Copy `.env.example` to `.env` and update `DATABASE_URL` and `DJANGO_SECRET_KEY`.

### 2. Install backend dependencies

From the project root:

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
python backend/manage.py migrate
```

### 3. Train the ML model

The application does not contain generated model binaries. Train the ensemble once:

```bash
python ml/train.py
```

Optional training controls are `START_DATE`, `END_DATE` and `MAX_TRAIN_ROWS`. Training downloads historical native 3-hour modelled pollutant data from Open-Meteo. It requires internet access and can take time depending on the requested date range.

### 4. Start Django

```bash
python backend/manage.py runserver 127.0.0.1:8000
```

The API health endpoint is `http://127.0.0.1:8000/api/health/`. The dashboard opens with Kolkata as an explicit example city; this is a real provider lookup, not a claim about the user's location. Change it with the city search.

### 5. Refresh the nationwide station network

Add a data.gov.in API key to `.env` (`DATA_GOV_IN_API_KEY`). Then run:

```bash
python backend/manage.py refresh_station_network
```

This syncs the CPCB station directory and its timestamped pollutant records into PostgreSQL. Run it using Windows Task Scheduler or cron, preferably hourly to match the source's published update granularity. On Windows, create a Basic Task that runs `scripts\refresh_stations_windows.bat` every 60 minutes. On Linux, the included `scripts/refresh_stations_linux.sh` can be scheduled; an example cron entry is:

```cron
0 * * * * cd /path/to/AtmoIQ && /path/to/AtmoIQ/.venv/bin/python backend/manage.py refresh_station_network
```

OpenAQ stations are also added to the directory when a city/nearby-stations lookup discovers them; this command currently performs the nationwide CPCB sync, not a nationwide OpenAQ sensor crawl.

### 6. Install and start React

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the local Vite address (normally `http://localhost:5173`). Vite forwards `/api` and `/media` requests to Django on port `8000` during development.

## Monitoring station API keys

City search and the Open-Meteo city forecast work without an API key. The CPCB/data.gov.in and OpenAQ station sources are optional and need their respective API credentials in `.env`:

- `DATA_GOV_IN_API_KEY`
- `OPENAQ_API_KEY`

When a station provider is not configured or returns no records, AtmoIQ says so instead of inventing station measurements.

## Building historical data

Station history is saved when the station endpoint retrieves readings. To collect it regularly without adding a task queue, run this Django command from the project root:

```bash
python backend/manage.py collect_station_history --cities Kolkata,Dhanbad,Delhi,Mumbai
```

Run it manually or schedule it with the operating system's existing task scheduler. The history and anomaly screens remain sparse until enough actual station observations have been collected. They do not fabricate historical values.

## Hotspot moderation

Create an administrator account:

```bash
python backend/manage.py createsuperuser
```

Open `/admin/`, review pending hotspot reports and change the report status to `Verified` or `Rejected`. New reports are not presented as verified incidents.

## Tests and checks

Run the application tests against the configured PostgreSQL database:

```bash
python backend/manage.py test air_quality
python -m unittest discover -s ml/tests
```

These tests use the configured PostgreSQL database. Create a separate test database or grant the development PostgreSQL user permission to create test databases.

Frontend production build:

```bash
cd frontend
npm run build
```

## API endpoints

| Method          | Endpoint                               | Purpose                                                                                         |
| --------------- | -------------------------------------- | ----------------------------------------------------------------------------------------------- |
| GET             | `/api/health/`                         | Database and model-artifact availability                                                        |
| GET             | `/api/city/?city=Kolkata`              | Current pollutant snapshot and model estimate                                                   |
| GET             | `/api/forecast/?city=Kolkata`          | Native 3-hour provider points, 1/3/6/24-hour horizon status and lowest available forecast point |
| GET             | `/api/stations/?city=Kolkata`          | Nearby CPCB/OpenAQ monitoring stations                                                          |
| GET             | `/api/network/india/`                  | Nationwide stored station directory and latest observations                                     |
| GET             | `/api/hotspots/detected/`              | Recent threshold-based station hotspot flags                                                    |
| GET             | `/api/advice/?aqi=150`                 | General AQI health guidance                                                                     |
| GET             | `/api/route/?start=Dhanbad&end=Ranchi` | Compare up to three available driving routes against nearby station readings                    |
| GET             | `/api/reports/pdf/?city=Kolkata`       | Download a city pollution snapshot as PDF                                                       |
| POST            | `/api/predict/`                        | Manual ML prediction                                                                            |
| POST            | `/api/sensitivity/`                    | ±20% one-feature-at-a-time sensitivity                                                          |
| GET             | `/api/ml/metrics/`                     | Held-out model evaluation metrics                                                               |
| GET             | `/api/history/?city=Kolkata&days=30`   | Stored station and forecast history                                                             |
| GET             | `/api/anomalies/?city=Kolkata`         | Station-specific statistical spike flags                                                        |
| GET/POST        | `/api/hotspots/`                       | Community hotspot report listing and submission                                                 |
| GET/POST/DELETE | `/api/exposure/`                       | Personal activity history                                                                       |

## Scientific and product limitations

- The existing training targets are CPCB-breakpoint proxy AQI values derived from Open-Meteo CAMS modelled concentrations. They are not official CPCB station AQI labels.
- The model's held-out RMSE/MAE/R² describe performance against those proxy labels. They must not be presented as verified field accuracy.
- Ensemble spread indicates model disagreement, not a calibrated probability or guaranteed prediction interval.
- Open-Meteo concentrations are model outputs, not direct local sensor readings.
- Station readings can have different observation times and supported pollutants. Missing or ambiguous values are left blank.
- The nationwide map depends on the configured CPCB/data.gov.in resource and successful scheduled sync. OpenAQ entries are discovered during city lookups, not a complete nationwide OpenAQ crawl.
- Automatic browser refresh intervals only reload AtmoIQ data; they do not force CPCB, OpenAQ or CAMS to publish a new reading. CAMS forecasts are model outputs and provider cadence can be slower than browser polling.
- Hotspot screening uses fixed concentration thresholds and recent stored station data. It is not an official hotspot classifier.
- The route finder depends on public OSRM availability and compares at most three provider-returned road alternatives. Station readings within 20 km are a coarse proxy for roadside conditions; no reading means the app falls back to shortest travel time.
- PDF reports are point-in-time summaries of modelled city concentrations and proxy AQI, not certified pollution certificates.
- Historical trends and anomaly detection need repeated station observations. Use the collection command on a schedule if persistent history is required.
- Cleaner-time guidance is a comparison of modelled estimates, not a guarantee of safe outdoor air.
- Personal activity history is approximate context only, not a personal pollution-dose estimate.
- Community reports are unverified until moderated.

See `DATA_SOURCES.md` and `DEPLOYMENT.md` for additional notes.
