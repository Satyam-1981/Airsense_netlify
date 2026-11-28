# AtmoIQ data sources and interpretation

AtmoIQ keeps measured station observations separate from modelled city and forecast data. Each screen shows the applicable source and timestamp where available.

## Current city snapshot and forecast

**Open-Meteo Air Quality API** (https://open-meteo.com/en/docs/air-quality-api) supplies CAMS Global modelled PM2.5, PM10, nitrogen dioxide, sulphur dioxide, carbon monoxide and ozone estimates. Ammonia is only available in the CAMS European forecast, not the CAMS Global domain used for India; AtmoIQ leaves city-level NH3 blank and excludes it from the ML feature set. Station providers may still report NH3, which is retained in station history. AtmoIQ retains only native 3-hour CAMS timestamps (the API may expose interpolated hourly timestamps, which are discarded). PM2.5, PM10, NO2 and SO2 use an 8-point 24-hour mean with at least 6 valid samples. CO and O3 use a maximum three-sample approximation to the CPCB 8-hour window, clearly treated as approximate. Missing values remain missing and are not imputed.

These are modelled atmospheric concentrations. They are not direct local sensor observations or official CPCB values. Open-Meteo documents the CAMS Global atmospheric composition forecast as approximately 45 km spatial resolution, three-hour temporal resolution and updated twice daily. A provider API response with hourly timestamps should not be mistaken for independent hourly local measurements.

## City lookup

**Open-Meteo Geocoding API** resolves a city name to coordinates. AtmoIQ selects an Indian result and shows the resolved city and state.

## Monitoring stations

**CPCB/data.gov.in** (https://www.data.gov.in/resource/real-time-air-quality-index-various-locations) can provide Indian monitoring station metadata and reported pollutant values through the configured resource. It requires a data.gov.in API key and the configured resource identifier. The official dataset page lists hourly granularity and warns that field-instrument values may occasionally be abnormal or erroneous; AtmoIQ does not silently smooth or replace those observations.

**OpenAQ v3** (https://docs.openaq.org/api/operations/location_latest_get_v3_locations__locations_id__latest_get) can provide supplementary monitoring locations and latest sensor readings. It requires an OpenAQ API key. Concentration values are normalized only for supported mass-concentration units. ppm/ppb values are skipped when molecular-weight and environmental conditions are not available for safe conversion. OpenAQ documents that its `latest` endpoint returns the last measurement in the sensor series, which is not always the most recently ingested value when upstream data arrives out of order.

Station directory entries are stored separately from station observations in PostgreSQL. For OpenAQ, AtmoIQ retains a timestamp for each pollutant because different sensors at one location can report at different times; the station-level timestamp is only the newest timestamp among those pollutant readings. The `refresh_station_network` management command pages through the configured CPCB/data.gov.in resource to refresh the national directory and timestamped records. OpenAQ stations are added when a city/nearby-station lookup discovers them; this build does not crawl the entire OpenAQ network nationwide. The map reads the stored directory and latest available observation. Provider observation timestamps are retained separately from directory-sync and last-fetch times. Schedule `refresh_station_network` using Windows Task Scheduler or cron (preferably hourly), and schedule `collect_station_history` for city-specific repeated samples if desired.

## Machine learning

`ml/train.py` obtains historical CAMS pollutant concentrations for a fixed set of Indian cities, derives CPCB-breakpoint proxy targets and trains Random Forest, Gradient Boosting and KNN regressors. A chronological split is used, with validation-derived model weights and held-out test metrics. Training uses native 3-hour CAMS points only, requires all six supported features, and does not impute missing values. The CO/O3 target sub-indices use an explicitly approximate three-sample window because the global source is not hourly.

The AQI target is a model-derived proxy. It is not a set of official measured CPCB AQI labels. The reported metrics therefore describe agreement with the constructed proxy target and should not be represented as real-world CPCB accuracy.

The prediction reliability display uses ensemble spread, input completeness and held-out proxy RMSE. It is not a calibrated probability or prediction interval. The sensitivity panel perturbs one input at a time and reruns the same ensemble; it is not causal attribution or SHAP.

## Historical trends and anomalies

Historical charts use only station observations actually saved in the PostgreSQL database. Records are grouped by source, station and pollutant rather than averaging different locations together. Sparse or missing history is shown as a data gap.

Anomaly flags compare a station's latest stored pollutant value with its own recent baseline using the median and median absolute deviation. At least ten earlier observations are required. A statistical outlier is a signal for attention, not proof of a pollution event or its source.

## Community reports and personal activity

Community hotspot reports are supplied by users and are unverified until a Django administrator reviews them. They are not official reports or measured pollution data.

Personal activity records pair a user-entered activity and duration with the current area-level values, when available. They are not personal sensor data, measured inhaled dose or medical advice.

## Health guidance

The broad AQI category meanings and health-impact descriptions are based on the Central Pollution Control Board's National AQI information: https://airquality.cpcb.gov.in/ccr_docs/About_AQI.pdf. AtmoIQ guidance is general information only. Its own modelled AQI proxy is not an official station AQI reading, and users should check official local advisories.

## Nationwide hotspot screening and route comparison

The map's potential-hotspot layer applies fixed screening thresholds to recent stored station values: PM2.5 at or above 60 µg/m³ or PM10 at or above 100 µg/m³. It is an explainable filter, not a learned event classifier, official incident, or proof of cause.

The comparative-route page uses the public OSRM driving router (https://project-osrm.org/) for up to three route alternatives. It samples route geometry and finds stored station PM2.5 values within 20 km of sampled points, requiring the PM2.5-specific timestamp to be no older than 48 hours. It ranks the alternatives by the average of those station values; if no usable readings are found, it falls back to the shortest travel time. This coarse comparison is not a continuous roadside pollution measurement and may not represent exposure along the full route.

The PDF report uses the same Open-Meteo CAMS modelled city concentrations and AtmoIQ proxy AQI estimate as the dashboard. It is a dated informational snapshot, not an official report or certificate.
