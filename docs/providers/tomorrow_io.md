# Tomorrow.io

## Official docs
- Forecast API: https://docs.tomorrow.io/reference/weather-forecast
- Realtime API: https://docs.tomorrow.io/reference/realtime-weather
- Data layers (available fields): https://docs.tomorrow.io/reference/data-layers-core
- FAQ on hourly forecast horizon (timesteps): https://docs.tomorrow.io/reference/hourly-forecast-up-to-120-hours

## Auth
- API key required.
- Env var: `WX_TOMORROW_IO_API_KEY`

## Endpoints

Observation (realtime)
- `GET https://api.tomorrow.io/v4/weather/realtime`

Hourly + daily forecasts
- `GET https://api.tomorrow.io/v4/weather/forecast`

## Required query params
- `location=lat,lon`
- `apikey`
- `units=metric`
- `timesteps=1h` for hourly
- `timesteps=1d` for daily

## Response fields used (examples)

Observation
- `data.time`
- `location.lat`, `location.lon`, `location.name`
- `data.values.temperature`, `temperatureApparent`, `dewPoint`, `humidity`, `pressureSurfaceLevel`
- `data.values.windSpeed`, `windDirection`, `windGust`
- `data.values.visibility`, `cloudCover`, `cloudBase`, `cloudCeiling`
- `data.values.pressureSeaLevel`, `altimeterSetting`
- `data.values.uvIndex`, `uvHealthConcern`
- `data.values.precipitationProbability`
- `data.values.rainIntensity`, `snowIntensity`, `sleetIntensity`, `freezingRainIntensity`
- `data.values.weatherCode` (condition code)

Forecasts
- `timelines.hourly[].time` + `timelines.hourly[].values.*`
- `timelines.daily[].time` + `timelines.daily[].values.*`

Daily values are typically aggregates (e.g., `temperatureMax`, `temperatureMin`,
`temperatureAvg`, `temperatureApparentAvg`) depending on the data layers returned. Contract tests should
capture which layers are returned and map what is available.

Common hourly/daily fields we normalize when present:
- `dewPoint`, `humidity`, `visibility`, `cloudCover`, `cloudBase`, `cloudCeiling`
- `pressureSeaLevel`, `pressureSurfaceLevel`, `altimeterSetting`
- `rainAccumulation`, `snowAccumulation`, `sleetAccumulation`, `iceAccumulation` (+ LWE variants)
- `rainIntensity`, `snowIntensity`, `sleetIntensity`, `freezingRainIntensity`
- `snowDepth`, `evapotranspiration`
- `uvIndex`, `uvHealthConcern`

## Normalization notes
- Requests use `units=metric` to align with canonical units.
- Wind speeds are in m/s; convert to kph.
- Pressure is in hPa; convert to kPa.
- Precipitation intensities are in mm/hr; if a total is needed, scale by interval duration.
- Weather codes are mapped to text condition in normalization.

## Contract cassettes (planned)
- `tomorrow_io_observation.yaml`
- `tomorrow_io_forecast_hourly.yaml`
- `tomorrow_io_forecast_daily.yaml`
