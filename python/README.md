# AirSense Python API

This directory is the complete backend. Install dependencies with `pip install -r requirements.txt`, run `uvicorn main:app --reload`, and visit `/docs` for the API.

Train the optional scikit-learn ensemble with `python train.py`. It writes model and metrics artifacts into `artifacts/` (ignored by Git). Until then, the API explicitly uses CPCB breakpoint calculations rather than claiming an untrained ML prediction.

All model labels are derived from Open-Meteo CAMS modelled concentrations and are not measured CPCB station AQI.
