# EcoWitt (Cloud API)

EcoWitt is used as an optional **ground-truth observation** source (your own weather station).

## Auth / configuration

Environment variables:

- `WX_ECOWITT_API_KEY`
- `WX_ECOWITT_APPLICATION_KEY`
- `WX_ECOWITT_DEVICE_MAC` (the station/gateway MAC used by EcoWitt Cloud)
- Optional: `WX_ECOWITT_STATION` (friendly name stored in `data_points.station`)

## Endpoint(s)

### Real-time observation

- `GET https://api.ecowitt.net/api/v3/device/real_time`
  - Query:
    - `application_key`
    - `api_key`
    - `mac`
    - `call_back=all` (request all available fields)

Normalization happens in `wxbench.domain.mappers.ecowitt.map_ecowitt_realtime`.

## Fields used (JSON paths)

Top-level:

- Observation timestamp:
  - `$.time` (fallback: `$.data.time`)

Core observation fields:

- Outdoor temperature:
  - `$.data.outdoor.temperature.value` + `unit`
- Outdoor humidity:
  - `$.data.outdoor.humidity.value`
- Wind speed:
  - `$.data.wind.wind_speed.value` + `unit`
- Wind gust:
  - `$.data.wind.wind_gust.value` + `unit`
- Wind direction:
  - `$.data.wind.wind_direction.value`
- Pressure (relative / sea-level):
  - `$.data.pressure.relative.value` + `unit`
- Pressure (absolute):
  - `$.data.pressure.absolute.value` + `unit`
- Rainfall:
  - `$.data.rainfall.hourly.value` + `unit`
  - `$.data.rainfall.daily.value` + `unit`
  - `$.data.rainfall.weekly.value` + `unit`
  - `$.data.rainfall.monthly.value` + `unit`
  - `$.data.rainfall.yearly.value` + `unit`
  - `$.data.rainfall.event.value` + `unit`
- UV index:
  - `$.data.solar_and_uvi.uvi.value`
- Solar radiation:
  - `$.data.solar_and_uvi.solar.value` + `unit`

## Unit conversion

EcoWitt payloads include `unit` strings in many places. The mapper converts into the internal units:

- temperature → °C
- wind → km/h
- pressure → kPa
- precipitation → mm

Unknown/missing unit strings are treated conservatively (assume the numeric value is already in the target unit).

## Contract test cassette (planned)

- `ecowitt_observation.yaml`

