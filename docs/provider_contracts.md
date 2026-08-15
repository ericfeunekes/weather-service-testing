# Provider contract references

Use this page to locate each implemented HTTP adapter, its recorded contract, and its provider note. Contract tests replay the cassettes under `tests/contract/cassettes/`.

| Provider | Implemented adapter entrypoints | Recorded contract | Provider note |
| --- | --- | --- | --- |
| AccuWeather | `fetch_accuweather_location`, `fetch_accuweather_observation`, `fetch_accuweather_hourly_forecast`, `fetch_accuweather_daily_forecast`, `fetch_accuweather_minute_forecast` | `accuweather_*.yaml` | [AccuWeather](providers/accuweather.md) |
| Ambient Weather | `fetch_ambient_weather_observation`, `fetch_ambient_weather_history` | `ambient_weather_*.yaml` | [Ambient Weather](providers/ambient_weather.md) |
| Ecowitt | `fetch_ecowitt_observation` | No VCR cassette | [Ecowitt](providers/ecowitt.md) |
| MSC GeoMet | `fetch_msc_geomet_observation`, `fetch_msc_geomet_forecast` | `msc_geomet_*.yaml` | [MSC GeoMet](providers/msc_geomet.md) |
| MSC RDPS PROGNOS | `fetch_msc_rdps_prognos_forecast` | `msc_rdps_prognos_forecast.yaml` | [MSC RDPS PROGNOS](providers/msc_rdps_prognos.md) |
| OpenWeather | `fetch_openweather_observation`, `fetch_openweather_forecast`, `fetch_openweather_onecall_hourly`, `fetch_openweather_onecall_daily` | `openweather_*.yaml` | [OpenWeather](providers/openweather.md) |
| Tomorrow.io | `fetch_tomorrow_io_observation`, `fetch_tomorrow_io_forecast`, `fetch_tomorrow_io_daily_forecast` | `tomorrow_io_*.yaml` | [Tomorrow.io](providers/tomorrow_io.md) |
| WeatherKit | `fetch_weatherkit_bundle` | `weatherkit_weather.yaml` | [WeatherKit](providers/weatherkit.md) |

All adapters accept an injected `httpx.Client`, use the shared retry and timeout policy, validate payload shape, then map into domain models. The pipeline captures raw responses before mapping.

## Contract boundary

The contract suite asserts request shape and maps replayed payloads through the actual adapters. Use it to change an endpoint, query parameter, relied-on response field, or mapping.

```bash
pytest tests/contract -q
```

Record live traffic only when intentionally refreshing a contract:

```bash
WX_VCR_RECORD_MODE=all pytest tests/contract -q
```

Export credentials only for authenticated providers under test. Cassettes must redact authorization headers, keys, tokens, and station identifiers.

## Notes

- MSC GeoMet uses its `citypageweather-realtime` collection for both adapter operations.
- MSC RDPS PROGNOS selects an available model cycle, using the dated archive when fallback crosses UTC midnight, then retrieves station-point GeoJSON by lead hour.
- Ecowitt is implemented in the pipeline and documented, but currently has no recorded contract. Add one before treating its boundary as replay-proven.
