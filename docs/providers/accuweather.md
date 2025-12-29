# AccuWeather

## Official docs
- Locations API (location key lookup): https://developer.accuweather.com/accuweather-locations-api
- Current Conditions API: https://developer.accuweather.com/current-conditions-api
- Forecast API: https://developer.accuweather.com/accuweather-forecast-api
- Hourly 12-hour endpoint: https://developer.accuweather.com/accuweather-forecast-api/apis/get/forecasts/v1/hourly/12hour/%7BlocationKey%7D
- Daily 1-day endpoint: https://developer.accuweather.com/accuweather-forecast-api/apis/get/forecasts/v1/daily/1day/%7BlocationKey%7D

## Auth
- API key required.
- Env var: `WX_ACCUWEATHER_API_KEY`

## Endpoints

Location key lookup (required for all other calls)
- `GET http://dataservice.accuweather.com/locations/v1/cities/geoposition/search`

Observation (current conditions)
- `GET http://dataservice.accuweather.com/currentconditions/v1/{locationKey}`

Hourly forecast
- `GET http://dataservice.accuweather.com/forecasts/v1/hourly/12hour/{locationKey}`

Daily forecast
- `GET http://dataservice.accuweather.com/forecasts/v1/daily/1day/{locationKey}`

## Required query params
- `apikey`
- `q=lat,lon` for geoposition search
- `metric=true` for metric units
- Optional: `details=true` for richer payloads

## Response fields used (examples)

Location lookup
- `Key` (location key)
- `GeoPosition.Latitude`, `GeoPosition.Longitude`

Current conditions
- `LocalObservationDateTime` or `EpochTime`
- `Temperature.Metric.Value`
- `RealFeelTemperature.Metric.Value`
- `RealFeelTemperatureShade.Metric.Value`
- `ApparentTemperature.Metric.Value`
- `WindChillTemperature.Metric.Value`
- `WetBulbTemperature.Value`
- `WetBulbGlobeTemperature.Value`
- `RelativeHumidity`
- `IndoorRelativeHumidity`
- `Pressure.Metric.Value`
- `Wind.Speed.Metric.Value`, `Wind.Direction.Degrees`
- `WindGust.Speed.Metric.Value`
- `Visibility.Metric.Value`
- `Ceiling.Metric.Value`
- `CloudCover`
- `PrecipitationSummary.Precipitation.Metric.Value`
- `Precip1hr.Metric.Value`
- `UVIndex`
- `UVIndexFloat`
- `WeatherIcon` (condition code)
- `PrecipitationType`
- `PressureTendency.LocalizedText`
- `WeatherText`

Hourly forecast (12h)
- `DateTime` or `EpochDateTime`
- `Temperature.Value`
- `RealFeelTemperature.Value`
- `RealFeelTemperatureShade.Value`
- `DewPoint.Value`
- `Visibility.Value`
- `Ceiling.Value`
- `WetBulbTemperature.Value`
- `WetBulbGlobeTemperature.Value`
- `RelativeHumidity`
- `PrecipitationProbability`
- `ThunderstormProbability`, `RainProbability`, `SnowProbability`, `IceProbability`
- `TotalLiquid.Value`, `Rain.Value`, `Snow.Value`, `Ice.Value`
- `Wind.Speed.Value`, `Wind.Direction.Degrees`
- `WindGust.Speed.Value`
- `UVIndex` / `UVIndexFloat`
- `IconPhrase` / `ShortPhrase`
- `WeatherIcon` (condition code)

Daily forecast (1d)
- `Date` or `EpochDate`
- `Temperature.Minimum.Value`, `Temperature.Maximum.Value`
- `Day.RealFeelTemperature.Average.Value`
- `Day.PrecipitationProbability`, `Day.Rain.Value`, `Day.Snow.Value`
- `Day.ThunderstormProbability`, `Day.RainProbability`, `Day.SnowProbability`, `Day.IceProbability`
- `Day.CloudCover`, `Day.RelativeHumidity.Average`
- `Day.Evapotranspiration.Value`, `Day.SolarIrradiance.Value`, `HoursOfSun`
- `Day.WetBulbTemperature.Average.Value`, `Day.WetBulbGlobeTemperature.Average.Value`
- `Day.Wind.Speed.Value`, `Day.Wind.Direction.Degrees`
- `Day.WindGust.Speed.Value`
- `Day.UVIndex`
- `Day.IconPhrase` / `Day.ShortPhrase`

## Normalization notes
- Request `metric=true` and store canonical units (C, kPa, kph, mm, km, deg).
- AccuWeather provides separate Metric/Imperial; use Metric values when present.

## Contract cassettes (planned)
- `accuweather_location_search.yaml`
- `accuweather_observation.yaml`
- `accuweather_forecast_hourly.yaml`
- `accuweather_forecast_daily.yaml`
