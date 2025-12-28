# Provider contract references

This document links adapter entrypoints to the recorded cassettes and the provider spec notes they rely on.

## OpenWeather
- **Adapter functions:** `wxbench.providers.openweather.fetch_openweather_observation`, `wxbench.providers.openweather.fetch_openweather_forecast`
- **Endpoints:** `GET /weather`, `GET /onecall` (planned)
- **Cassette files:** `tests/contract/cassettes/openweather_observation.yaml`, `tests/contract/cassettes/openweather_onecall_hourly.yaml`, `tests/contract/cassettes/openweather_onecall_daily.yaml`
- **Spec doc:** `docs/providers/openweather.md`

## Tomorrow.io
- **Adapter functions:** `wxbench.providers.tomorrow_io.fetch_tomorrow_io_observation`, `wxbench.providers.tomorrow_io.fetch_tomorrow_io_forecast`
- **Endpoints:** `GET /realtime`, `GET /forecast`
- **Cassette files:** `tests/contract/cassettes/tomorrow_io_observation.yaml`, `tests/contract/cassettes/tomorrow_io_forecast_hourly.yaml`, `tests/contract/cassettes/tomorrow_io_forecast_daily.yaml`
- **Spec doc:** `docs/providers/tomorrow_io.md`

## MSC GeoMet
- **Adapter functions:** `wxbench.providers.msc_geomet.fetch_msc_geomet_observation`, `wxbench.providers.msc_geomet.fetch_msc_geomet_forecast`
- **Endpoints:** `GET /collections/citypageweather-realtime/items`
- **Cassette files:** `tests/contract/cassettes/msc_geomet_observation.yaml`, `tests/contract/cassettes/msc_geomet_forecast.yaml`
- **Spec doc:** `docs/providers/msc_geomet.md`
- **OpenAPI snapshot:** `specs/msc-geomet.json`

## MSC RDPS PROGNOS
- **Adapter functions:** `wxbench.providers.msc_rdps_prognos.fetch_msc_rdps_prognos_forecast`
- **Endpoints:** Datamart GeoJSON files under `/today/model_rdps/stat-post-processing/{HH}/{LEAD}/`
- **Cassette files:** `tests/contract/cassettes/msc_rdps_prognos_forecast.yaml`
- **Spec doc:** `docs/providers/msc_rdps_prognos.md`

## AccuWeather
- **Adapter functions:** planned (location lookup, current conditions, hourly, daily)
- **Endpoints:** `GET /locations/v1/cities/geoposition/search`, `GET /currentconditions/v1/{locationKey}`, `GET /forecasts/v1/hourly/12hour/{locationKey}`, `GET /forecasts/v1/daily/1day/{locationKey}`
- **Cassette files:** `tests/contract/cassettes/accuweather_location_search.yaml`, `tests/contract/cassettes/accuweather_observation.yaml`, `tests/contract/cassettes/accuweather_forecast_hourly.yaml`, `tests/contract/cassettes/accuweather_forecast_daily.yaml`
- **Spec doc:** `docs/providers/accuweather.md`

## Ambient Weather
- **Adapter functions:** `wxbench.providers.ambient_weather.fetch_ambient_weather_observation`
- **Endpoints:** `GET /v1/devices`
- **Cassette files:** `tests/contract/cassettes/ambient_weather_observation.yaml`
- **Spec doc:** `docs/providers/ambient_weather.md`
