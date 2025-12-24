# Provider contract references

This document links adapter entrypoints to the recorded cassettes and the provider spec notes they rely on.

## OpenWeather
- **Adapter functions:** `wxbench.providers.openweather.fetch_openweather_observation`, `wxbench.providers.openweather.fetch_openweather_forecast`
- **Endpoints:** `GET /weather`, `GET /forecast`
- **Cassette files:** `tests/contract/cassettes/openweather_observation.yaml`, `tests/contract/cassettes/openweather_forecast.yaml`
- **Spec doc:** `specs/openweather.md`

## Tomorrow.io
- **Adapter functions:** `wxbench.providers.tomorrow_io.fetch_tomorrow_io_observation`, `wxbench.providers.tomorrow_io.fetch_tomorrow_io_forecast`
- **Endpoints:** `GET /realtime`, `GET /forecast`
- **Cassette files:** `tests/contract/cassettes/tomorrow_io_observation.yaml`, `tests/contract/cassettes/tomorrow_io_forecast.yaml`
- **Spec doc:** `specs/tomorrow_io.md`

## MSC GeoMet
- **Adapter functions:** `wxbench.providers.msc_geomet.fetch_msc_geomet_observation`, `wxbench.providers.msc_geomet.fetch_msc_geomet_forecast`
- **Endpoints:** `GET /collections/observations/point`, `GET /collections/forecasts/point`
- **Cassette files:** `tests/contract/cassettes/msc_geomet_observation.yaml`, `tests/contract/cassettes/msc_geomet_forecast.yaml`
- **Spec doc:** `specs/msc_geomet.md`
- **OpenAPI snapshot:** `specs/msc-geomet.json`
