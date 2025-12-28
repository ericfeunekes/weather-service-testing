# OpenWeather

## Official docs
- Current weather: https://docs.openweather.co.uk/current
- One Call 3.0: https://openweathermap.org/api/one-call-3
- One Call 3.0 (API reference): https://docs.openweather.co.uk/api/one-call-3

## Auth
- API key required.
- Env var: `WX_OPENWEATHER_API_KEY`

## Endpoints

Observation (current conditions)
- `GET https://api.openweathermap.org/data/2.5/weather`

Hourly + daily forecasts
- `GET https://api.openweathermap.org/data/3.0/onecall`

## Required query params
- `lat`, `lon`, `appid`
- `units=metric` (preferred)

## Response fields used (examples)

Observation (current)
- `dt`
- `coord.lat`, `coord.lon`
- `main.temp`, `main.feels_like`, `main.pressure`, `main.humidity`
- `wind.speed`, `wind.deg`, `wind.gust`
- `visibility`
- `rain.1h`, `snow.1h`
- `clouds.all`
- `weather[0].description` (condition)
- `weather[0].id` (condition code)

Hourly (One Call)
- `hourly[].dt`
- `hourly[].temp`, `hourly[].feels_like`, `hourly[].pressure`, `hourly[].humidity`, `hourly[].dew_point`
- `hourly[].wind_speed`, `hourly[].wind_deg`, `hourly[].wind_gust`
- `hourly[].visibility`, `hourly[].clouds`, `hourly[].uvi`
- `hourly[].pop`, `hourly[].rain.1h`, `hourly[].snow.1h`
- `hourly[].weather[0].description`
- `hourly[].weather[0].id`

Daily (One Call)
- `daily[].dt`
- `daily[].temp.day`, `daily[].temp.min`, `daily[].temp.max`, `daily[].feels_like.day`
- `daily[].pressure`, `daily[].humidity`, `daily[].dew_point`
- `daily[].wind_speed`, `daily[].wind_deg`, `daily[].wind_gust`
- `daily[].clouds`, `daily[].uvi`
- `daily[].pop`, `daily[].rain`, `daily[].snow`
- `daily[].weather[0].description`
- `daily[].weather[0].id`

## Normalization notes
- If `units=metric` is not used, convert:
  - Kelvin -> C
  - hPa -> kPa
  - m/s -> kph
  - visibility meters -> km
- `pop` is 0..1 in One Call; store as percent.

## Contract cassettes (planned)
- `openweather_observation.yaml`
- `openweather_onecall_hourly.yaml`
- `openweather_onecall_daily.yaml`
