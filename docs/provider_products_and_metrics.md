# Provider products and metrics

Use this guide to query normalized provider data without comparing incompatible periods or units.

## Confirm actual coverage

Mappings determine possible metrics. Credentials, upstream responses, and run history determine what exists locally. Query the data before building a comparison.

```sql
SELECT provider, product_kind, metric_type, unit, COUNT(*) AS rows
FROM data_points
GROUP BY provider, product_kind, metric_type, unit
ORDER BY provider, product_kind, metric_type, unit;
```

## Implemented products

| Provider | Products exposed by adapters |
| --- | --- |
| AccuWeather | observation, hourly, daily, minutely forecast |
| Ambient Weather | observation and history |
| Ecowitt | observation |
| MSC GeoMet | observation and forecast |
| MSC RDPS PROGNOS | forecast |
| OpenWeather | observation, forecast, One Call hourly and daily forecast |
| Tomorrow.io | observation, hourly and daily forecast |
| WeatherKit | observation, hourly, daily, next-hour forecast, and alerts |

The stored `product_kind` values come from the mapper. Inspect the query above instead of inferring them from provider marketing names.

## Metric families

Common normalized metrics include:

- Temperature: `temperature_air`, `temperature_apparent`, `temperature_high`, `temperature_low`, and `dewpoint`.
- Precipitation: `precip_amount`, `precip_probability`, and precipitation-rate metrics.
- Wind: `wind_speed`, `wind_gust`, and `wind_direction`.
- Atmosphere: `pressure`, `pressure_sea_level`, `humidity`, `cloud_cover`, and `visibility`.
- Other: `condition`, `condition_code`, `uv_index`, `snow_depth`, and solar-radiation metrics.

The mapper source is authoritative for exact names and units: `src/wxbench/domain/mappers/`.

## Compare safely

1. Filter forecast periods by `valid_start_utc`, then select the desired `run_at_utc` vintage.
2. Keep `product_kind` consistent, or aggregate granular periods before comparing.
3. Do not compare amounts with rates.
4. Check `unit` rather than assuming provider conventions.
5. Treat snow amounts as liquid-water equivalent unless the metric is `snow_depth`.

For layout and timestamps, see the [data model and pipeline guide](data_model_and_pipeline.md).
