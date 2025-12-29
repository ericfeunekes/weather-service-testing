# Provider documentation

This directory documents provider-specific endpoints, required parameters, and field mappings used to
normalize data into the single `data_points` table described in ADR 0001.

Each provider page includes:
- Official documentation links
- Authentication requirements
- Endpoints for observations and forecasts (hourly, daily, or period-based depending on provider)
- Response fields used for normalization (with JSON paths)
- Unit conversion notes
- Contract test cassette names

## Provider pages

- `docs/providers/openweather.md`
- `docs/providers/tomorrow_io.md`
- `docs/providers/accuweather.md`
- `docs/providers/msc_geomet.md`
- `docs/providers/msc_rdps_prognos.md`
- `docs/providers/ambient_weather.md`

## Contract test intent

Contract tests capture a real API response in VCR cassettes for each endpoint and assert:
- Request shape (path + params)
- Presence of the fields we normalize
- Provider-specific invariants (e.g., timestamps, coordinates)

Component tests then replay those cassettes end-to-end to store raw payloads and normalized data points
into a dummy SQLite database.
