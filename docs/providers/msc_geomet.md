# MSC GeoMet (Environment and Climate Change Canada)

## Official docs
- GeoMet OGC API overview: https://eccc-msc.github.io/open-data/msc-geomet/readme_en/
- City page weather product (GeoMet + Datamart): https://eccc-msc.github.io/open-data/msc-data/citypage-weather/readme_citypageweather_en/
- City page weather Datamart update cadence: https://eccc-msc.github.io/open-data/msc-data/citypage-weather/readme_citypageweather-datamart_en/
- RDPS PROGNOS station post-processing (Datamart GeoJSON): https://eccc-msc.github.io/open-data/msc-data/nwp_rdps/readme_rdps-statpostproc-datamart_en/

## Auth
- No API key required.

## Endpoints

City page weather realtime collection
- `GET https://api.weather.gc.ca/collections/citypageweather-realtime/items`

## Required query params
- `bbox=lon_min,lat_min,lon_max,lat_max`
- `limit=1`
- `f=json`

We use a small bbox around the configured coordinates and take the first feature.
The returned feature contains both current conditions and forecast periods.

## Cadence
- City page weather is updated at least hourly (Datamart publishes new XML/GeoJSON updates on that cadence).

## Response fields used (examples)

Shared
- `geometry.coordinates[0]` (lon)
- `geometry.coordinates[1]` (lat)

Observation (from `properties` + `properties.currentConditions`)
- `stationIdentifier` / `station` / `identifier`
- `observationTime` / `time`
- `airTemperature`
- `dewpointTemperature`
- `wind.speed`, `wind.direction`
- `seaLevelPressure` / `pressure`
- `relativeHumidity`
- `visibility`
- `windChill`
- `presentWeather[].value/text/description`
- `precipitationLastHour`

Forecast (from `properties.forecastGroup` or `properties.periods`)
- `forecastIssueTime` / `issueTime`
- `periods[].start` / `startTime`
- `periods[].end` / `endTime`
- `periods[].temperature` / `temperatureHigh` / `temperatureLow`
- `periods[].probabilityOfPrecipitation` / `pop`
- `periods[].totalPrecipitation` / `precipitationAmount`
- `periods[].summary` / `textSummary`
- `periods[].wind.speed`, `periods[].wind.direction`
- `periods[].relativeHumidity`
- `periods[].uv`
- `periods[].windChill`

## Normalization notes
- Values are already metric (C, kPa, kph, mm).
- Forecast periods are typically day/night blocks (not true hourly). We store them as
  `forecast_hourly` for lead-time continuity and derive daily summaries separately.

## Other MSC sources
- **RDPS PROGNOS station forecasts (Datamart GeoJSON)**  
  Implemented separately in `docs/providers/msc_rdps_prognos.md` (hourly lead times, limited variables).
- **UMOS OGC API collections (RDPS/GDPS)**  
  Station point forecasts with limited variables and 3-hourly lead times.  
  Collections: https://api.weather.gc.ca/collections/umos-rdps-realtime?lang=en  
  https://api.weather.gc.ca/collections/umos-gdps-realtime?lang=en
- **Raw model grids (GRIB2)**  
  Full variable coverage and hourly cadence, but requires GRIB parsing + spatial interpolation.  
  RDPS (10km): https://eccc-msc.github.io/open-data/msc-data/nwp_rdps/readme_rdps-datamart_en/  
  HRDPS (2.5km): https://eccc-msc.github.io/open-data/msc-data/nwp_hrdps/readme_hrdps-datamart_en/

## Contract cassettes
- `msc_geomet_observation.yaml`
- `msc_geomet_forecast.yaml`
