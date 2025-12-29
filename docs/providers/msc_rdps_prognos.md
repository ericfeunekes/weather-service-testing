# MSC RDPS PROGNOS (Environment and Climate Change Canada)

## Official docs
- RDPS PROGNOS station post-processing (Datamart GeoJSON): https://eccc-msc.github.io/open-data/msc-data/nwp_rdps/readme_rdps-statpostproc-datamart_en/

## Auth
- No API key required.

## Dataset overview
- Station-point, statistically post-processed RDPS forecasts.
- Hourly lead times `PT000H` through `PT084H`.
- Variables provided: AirTemp, DewPoint, WindSpeed, WindDir.
- No precipitation, humidity, or pressure in this dataset.

## Endpoint pattern (Datamart)

```
GET https://dd.weather.gc.ca/today/model_rdps/stat-post-processing/{HH}/{LEAD}/{YYYYMMDD}T{HH}Z_MSC_RDPS-PROGNOS-{METHOD}-{VARIABLE}_{VERTICAL}_PT{LEAD}H.json
```

Where:
- `HH` is the model run hour: `00`, `06`, `12`, `18`.
- `LEAD` is a 3-digit hour lead: `000`-`084`.
- `METHOD` is per-variable (see below).
- `VARIABLE` is one of `AirTemp`, `DewPoint`, `WindSpeed`, `WindDir`.
- `VERTICAL` is `AGL-1.5m` (temperature/dewpoint) or `AGL-10m` (wind).

### Variable -> method mapping
- `AirTemp` -> `MLR` (AGL-1.5m)
- `DewPoint` -> `MLR` (AGL-1.5m)
- `WindSpeed` -> `LASSO` (AGL-10m)
- `WindDir` -> `WDLASSO2` (AGL-10m)

## Response fields used (examples)
- `geometry.coordinates` (lon, lat, elevation)
- `properties.prognos_station_id`
- `properties.reference_datetime` (model run time)
- `properties.forecast_datetime` (valid time)
- `properties.forecast_leadtime` (e.g., `PT012H`)
- `properties.forecast_value`
- `properties.unit`

## Normalization notes
- Units: temperature/dewpoint arrive in Kelvin -> convert to Celsius.
- Wind speed in `km/h` is already canonical (kph).
- Wind direction is degrees; normalize to integer degrees.
- We select the nearest station to the configured `WX_LAT/WX_LON`.
- We store `prognos_station_id` as the station identifier.
- We ingest all lead hours `0-84` each run and store hourly forecasts; daily is derived.
- Pulling the full 0-84 range requires 4 files per lead hour (~340 requests per run).

## Contract cassettes
- `msc_rdps_prognos_forecast.yaml`
