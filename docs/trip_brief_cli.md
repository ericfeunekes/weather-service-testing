# Trip brief CLI

Generate a route-weather brief using Google Routes, WeatherKit hourly forecasts, and optional MSC GeoMet observations.

## Required environment

Export these values before running the CLI. Keep secrets in your shell or a local ignored environment file.

```text
WX_GOOGLE_MAPS_API_KEY
WX_WEATHERKIT_TEAM_ID
WX_WEATHERKIT_SERVICE_ID
WX_WEATHERKIT_KEY_ID
WX_WEATHERKIT_KEY_PATH
```

`WX_WEATHERKIT_COUNTRY_CODE` is optional and defaults to `CA`.

## Route configuration

The default configuration is [configs/routes.yaml](../configs/routes.yaml). It supplies route presets, sampling defaults, route preferences, MSC mode, and timezone. Presets currently include `bathurst_to_halifax` and `halifax_to_martock`.

## Run

Use a preset route:

```bash
trip-brief --route bathurst_to_halifax --depart 2026-01-15T09:00
```

Or provide an ad-hoc origin and destination:

```bash
trip-brief --origin "Bathurst, NB" --destination "Halifax, NS" --depart 2026-01-15T09:00
```

Naive departure timestamps use the configured route timezone. An offset-bearing ISO timestamp keeps its supplied offset.

## Controls and output

| Option | Effect |
| --- | --- |
| `--distance-km` / `--time-cap-min` | Override sampling limits. |
| `--timezone` | Override the route timezone. |
| `--msc-mode none\|endpoints\|corridor` | Skip, sample route endpoints, or sample every route point. |
| `--output <path>` | Write Markdown instead of stdout. |
| `--pdf` / `--pdf-path <path>` | Write a PDF; default path is `reports/trip_brief.pdf`. |

The CLI supports Markdown output only. It fetches route geometry, samples points, estimates pass-through times, selects WeatherKit hourly periods, then renders a summary and per-point table.
