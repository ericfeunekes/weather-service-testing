# ADR 0002: MSC Forecast Sources + Scope

Date: 2025-12-28
Status: Accepted

## Context

We need Environment and Climate Change Canada (MSC) data that can be pulled hourly so we can
track how forecasts change over time and compare them to Ambient observations for scoring and
model training. We also want as many variables as possible, but we need to keep the ingestion
pipeline lightweight and deterministic.

MSC offers multiple datasets:
- City Page Weather (official public forecast product; period-based day/night blocks).
- Station point, statistically post-processed model forecasts (RDPS/HRDPS PROGNOS).
- UMOS station point forecasts (OGC API collections).
- Raw model grids (RDPS/HRDPS/GDPS) in GRIB2.

## Decision

1) **Use City Page Weather via the GeoMet OGC API** as the official MSC forecast and observation
   source for this project.
2) **Add RDPS PROGNOS station-point forecasts** as the middle-ground hourly feed (0-84h lead times).
3) **Ingest both hourly**, and store each run so we can evaluate how forecasts evolve over time.
4) **Treat City Page forecast periods as "period forecasts"** (not true hourly). We store them under
   `forecast_hourly` for lead-time continuity and derive daily summaries from those periods.
5) **Defer full-variable ingestion** (precip, humidity, pressure, etc.) until we choose a model-grid
   pipeline (GRIB2).

## Consequences

- We get official MSC forecasts plus true hourly lead times with limited variables.
- MSC City Page forecasts are day/night period blocks; they are not model-hourly.
- RDPS PROGNOS adds temperature, dew point, and wind; precip/humidity/pressure remain deferred.

## Alternatives Considered

- **RDPS PROGNOS (Datamart GeoJSON)**  
  Selected as the middle-ground hourly feed (implemented). Limited variables remain a known gap.

- **UMOS (OGC API)**  
  Station point forecasts with 3-hourly lead times and limited variables. Viable but not a
  significant improvement over City Page Weather for this project's goals.

- **Raw model grids (GRIB2)**  
  Full variables and hourly cadence, but requires GRIB parsing, spatial interpolation, and larger
  storage/compute. Deferred for now to keep scope minimal.

## Follow-up Work (Not Implemented)

- Decide if we want a dedicated `forecast_period` product kind to avoid labeling City Page forecasts
  as hourly.
- If we need "everything", design a GRIB2 ingestion pipeline and interpolation strategy.

## Related docs

- `docs/providers/msc_geomet.md`
- `docs/providers/msc_rdps_prognos.md`
