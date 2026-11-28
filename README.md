# AirSense — Air Quality Intelligence for India

AirSense is a React + TypeScript dashboard backed by **one Python FastAPI service**. The Python service owns all backend responsibilities: live data retrieval, city lookup, station discovery, AQI calculations, forecasting, model training/inference, metrics and optional data.gov.in access.

## Architecture

- **Frontend:** React 19, TypeScript, Vite, TanStack Router and Recharts. It is a static web app; it contains no server-side API implementation.
- **Backend:** Python 3.11+, FastAPI and Pydantic.
- **ML:** scikit-learn Random Forest, Gradient Boosting and KNN weighted ensemble.
- **Data:** Open-Meteo Air Quality (no key for its public endpoint), optional OpenAQ v3 and data.gov.in.

## Run locally

### 1. Python API

```bash
cd python
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

API docs: <http://127.0.0.1:8000/docs>

### 2. Frontend

In another terminal, from the repository root:

```bash
npm install
cp .env.example .env
npm run dev
```

Open <http://localhost:5173>. Set `VITE_API_BASE_URL` in `.env` if the API runs elsewhere. Restart Vite after changing environment variables.

## Model training

The project ZIP intentionally does not include a trained model binary. Train one locally (requires internet access and may take some time):

```bash
cd python
python train.py
```

Training downloads historical Open-Meteo CAMS pollutant concentrations, builds rolling concentration features and CPCB-breakpoint-derived proxy targets, evaluates a chronological split, and writes `python/artifacts/airsense_models.joblib` plus `metrics.json`. Restart the API after training so it loads the artifact.

Without a trained artifact, `/predict` uses a transparent CPCB-breakpoint calculation and labels the result accordingly. It does **not** pretend that a model has been trained. Model insights return a clear not-trained state until metrics exist.

## API endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | Service and model status |
| `GET /cities` | Supported city index |
| `GET /air-quality/{city}` | Latest available modelled pollutant values and AQI result |
| `POST /predict` | AQI calculation / trained ensemble prediction |
| `POST /predict/batch` | Batch prediction (up to 500 records) |
| `GET /forecast/{city}` | Five-day hourly forecast and AQI estimates |
| `GET /stations?city=Kolkata` | OpenAQ monitoring locations and latest readings |
| `GET /metrics` | Training metrics and model status |
| `GET /cpcb-observations?limit=50` | Optional raw data.gov.in resource records |
| `GET /docs` | Interactive API documentation |

## Environment variables

### Frontend build environment

- `VITE_API_BASE_URL`: public base URL of the Python API, without a trailing slash. This value is public and must not contain secrets.

### Python service environment

- `OPENAQ_API_KEY`: optional OpenAQ v3 key.
- `DATA_GOV_IN_API_KEY`: optional data.gov.in key.
- `DATA_GOV_IN_RESOURCE_ID`: optional selected data.gov.in resource ID.
- `CORS_ORIGINS`: comma-separated allowed frontend origins. Use the deployed frontend URL in production; `*` is convenient for local development.

## Deployment

### Python API on Render

The included `render.yaml` creates the Python web service. Connect the repository to Render and deploy the blueprint. Configure optional API keys and set `CORS_ORIGINS` to the frontend domain.

### Frontend on Vercel

Import the repository into Vercel. Use the repository root, framework preset **Vite**, build command `npm run build`, and output directory `dist`. Add `VITE_API_BASE_URL` with the deployed Render API URL. The included `vercel.json` supports client-side route fallback.

## Data quality and scientific limitations

Open-Meteo's air-quality service provides CAMS modelled pollutant concentrations, not direct station measurements. OpenAQ is a partial aggregation and may have missing or delayed readings. The training target is a **CPCB-breakpoint proxy derived from modelled concentrations**, not official CPCB ground-truth AQI. The reported metrics therefore measure agreement with that proxy only. Do not market them as validated CPCB station accuracy.

CPCB AQI reporting also depends on pollutant-specific averaging windows, data completeness and station quality controls. The live display is an educational estimate from the selected modelled data; it is not an official CPCB alert or a medical diagnosis. Validate source fields and units before using optional data.gov.in records as reference observations.

## Checks

```bash
npm run typecheck
npm run build
python -m compileall -q python
```
