# Ambient Weather

## Official docs
- Ambient Weather API docs (Postman): https://documenter.getpostman.com/view/321924/ambient-weather-api/2HTbHW
- Ambient Weather API FAQ: https://ambientweather.com/faqs/question/view/id/4763/

## Auth
- API key + application key required.
- Env vars: `WX_AMBIENT_API_KEY`, `WX_AMBIENT_APPLICATION_KEY`
- Optional device selector: `WX_AMBIENT_DEVICE_MAC`

## Endpoints

Observation (station devices)
- `GET https://api.ambientweather.net/v1/devices`

## Required query params
- `apiKey`
- `applicationKey`

## Response fields used (examples)

The endpoint returns a list of devices. Each device includes metadata plus a
`lastData` block with recent observations. Field availability depends on the
station model and sensors. Typical fields include:

- `info.name`, `info.location` (station identity)
- `lastData.dateutc` (observation timestamp)
- `lastData.tempf` (temperature)
- `lastData.dewptf`
- `lastData.humidity`
- `lastData.baromrelin` / `baromabsin` (pressure)
- `lastData.windspeedmph`, `windgustmph`, `winddir`
- `lastData.hourlyrainin`, `dailyrainin`
- `lastData.weeklyrainin`, `monthlyrainin`, `yearlyrainin`, `eventrainin`
- `lastData.tempinf`, `humidityin`, `dewPointin`
- `lastData.feelsLike`, `feelsLikein`
- `lastData.solarradiation`, `uv`
- `lastData.battin`, `battout`

Contract tests should record a real device payload and map whatever fields are
present into canonical metric types.

If multiple devices are returned, set `WX_AMBIENT_DEVICE_MAC` to force a specific
device; otherwise, the mapper selects the first device (sorted by MAC) for
deterministic behavior.

## Normalization notes
- Ambient Weather returns imperial units by default; convert to:
  - F -> C
  - mph -> kph
  - inHg -> kPa
  - inches -> mm

## Contract cassettes (planned)
- `ambient_weather_observation.yaml`
