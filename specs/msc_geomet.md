# MSC GeoMet API contract notes

- **Base URL:** `https://api.weather.gc.ca`
- **Endpoints used:**
  - `GET /collections/observations/point` (latest observation for a coordinate)
  - `GET /collections/forecasts/point` (point forecast periods)
- **Required query params:**
  - `lat` – latitude in decimal degrees
  - `lon` – longitude in decimal degrees
  - `f` – response format, set to `json`
- **Response fields mapped:**
  - Shared geometry: `geometry.coordinates[0]` (lon), `geometry.coordinates[1]` (lat)
  - Observation properties: `stationIdentifier`/`station`, `observationTime`/`time`, `airTemperature`, `dewpointTemperature`, `wind.speed`, `wind.direction`, `seaLevelPressure`/`pressure`, `relativeHumidity`, `visibility`, `presentWeather[].value/text/description`, `precipitationLastHour`
  - Forecast properties: `forecastIssueTime`/`issueTime`, `periods[].start`/`startTime`, `periods[].end`/`endTime`, `periods[].temperature`, `periods[].temperatureHigh`, `periods[].temperatureLow`, `periods[].probabilityOfPrecipitation`/`pop`, `periods[].totalPrecipitation`/`precipitationAmount`, `periods[].summary`/`textSummary`, `periods[].wind.speed`, `periods[].wind.direction`
- **Units and notes:**
  - Responses are already metric (temperatures in °C, wind in km/h, precipitation in mm) so mappers do not convert units.
  - Timestamps are ISO-8601 strings parsed as UTC.
