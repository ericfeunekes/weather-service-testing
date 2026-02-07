# WeatherKit

## Official docs
- WeatherKit REST API overview: https://developer.apple.com/documentation/weatherkitrestapi
- Request authentication (JWT): https://developer.apple.com/documentation/weatherkitrestapi/request-authentication-for-weatherkit-rest-api
- Weather endpoint: https://developer.apple.com/documentation/weatherkitrestapi/get-api-v1-weather-_language_-_latitude_-_longitude_
- DataSet values: https://developer.apple.com/documentation/weatherkitrestapi/dataset
- CurrentWeather fields: https://developer.apple.com/documentation/weatherkitrestapi/currentweather/currentweatherdata
- Hourly forecast fields: https://developer.apple.com/documentation/weatherkitrestapi/hourweatherconditions
- Daily forecast fields: https://developer.apple.com/documentation/weatherkitrestapi/dayweatherconditions

## Auth
- WeatherKit requires a signed JWT developer token (ES256) with:
  - Header: `alg`, `kid`, `id` (`TEAM_ID.SERVICE_ID`)
  - Claims: `iss` (Team ID), `sub` (Service ID), `iat`, `exp`
- Env vars:
  - `WX_WEATHERKIT_TEAM_ID`
  - `WX_WEATHERKIT_SERVICE_ID`
- `WX_WEATHERKIT_KEY_ID`
- `WX_WEATHERKIT_KEY_PATH`
- `WX_WEATHERKIT_COUNTRY_CODE` (required to request alerts)

## Endpoints

Weather (current + forecast data)
- `GET https://weatherkit.apple.com/api/v1/weather/{language}/{latitude}/{longitude}`

## Required query params
- `dataSets=currentWeather,forecastHourly,forecastDaily,forecastNextHour,weatherAlerts`
- `timezone=<IANA name>` (required for daily rollups)
- `countryCode` (required for weather alerts)

## Response fields used (examples)

Current weather (`currentWeather`)
- `metadata.latitude`, `metadata.longitude`
- `asOf`
- `temperature`, `temperatureApparent`, `temperatureDewPoint`
- `humidity`
- `pressure`
- `windSpeed`, `windDirection`, `windGust`
- `visibility`
- `cloudCover`
- `conditionCode`
- `precipitationIntensity`
- `uvIndex`
- `pressureTrend`

Hourly forecast (`forecastHourly.hours[]`)
- `forecastStart`
- `temperature`, `temperatureApparent`, `temperatureDewPoint`
- `humidity`
- `pressure`
- `windSpeed`, `windDirection`, `windGust`
- `visibility`
- `cloudCover`
- `uvIndex`
- `precipitationChance`
- `precipitationAmount`
- `snowfallIntensity`
- `conditionCode`

Daily forecast (`forecastDaily.days[]`)
- `forecastStart`, `forecastEnd`
- `temperatureMax`, `temperatureMin`
- `precipitationChance`, `precipitationAmount`
- `snowfallAmount`
- `maxUvIndex`
- `conditionCode`
- `daytimeForecast.windSpeed`, `daytimeForecast.windDirection` (optional for wind)
- `daytimeForecast.humidity`, `daytimeForecast.cloudCover` (optional)

Next hour (`forecastNextHour.minutes[]`, `forecastNextHour.summary[]`)
- `minutes[].startTime`
- `minutes[].precipitationChance`
- `minutes[].precipitationIntensity`
- `summary[].startTime` (end time inferred from next summary or `forecastEnd`)
- `summary[].condition`

Weather alerts (`weatherAlerts.alerts[]`)
- `id`
- `issuedTime`, `effectiveTime`, `expireTime`
- `eventOnsetTime`, `eventEndTime` (optional)
- `severity`, `certainty`, `urgency`
- `description`, `source`
- `responses` (array)
- `areaId`, `areaName`, `countryCode`
- `detailsUrl` (optional)

## Normalization notes
- Temperatures are already in Celsius.
- Pressure is in millibars (hPa); convert to kPa.
- Wind speed/gust is in km/h.
- Visibility is in meters; convert to km.
- Humidity and cloud cover are 0..1 fractions; convert to percent.
- Precipitation chance is 0..1; convert to percent.
- `conditionCode` is a string; stored as `condition` text.
- `precipitationIntensity` is a generic mm/hr rate without type; mapped to `precip_rate_rain`.
- Next-hour precipitation rates are mapped to precip-type-specific fields when `summary[].condition` is available; otherwise stored as `precip_rate_rain`.
- Weather alerts are normalized into alert data points (text metrics).

## Contract cassettes (planned)
- `weatherkit_weather.yaml`
