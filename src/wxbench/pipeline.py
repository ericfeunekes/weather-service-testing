"""Orchestration for fetching provider data and storing in SQLite."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional

import httpx

from wxbench.config import WxConfig
from wxbench.domain.aggregate import aggregate_daily_from_periods
from wxbench.domain.datapoints import (
    PRODUCT_FORECAST_DAILY,
    PRODUCT_FORECAST_HOURLY,
    observation_to_datapoints,
    forecast_to_datapoints,
)
from wxbench.domain.models import DataPoint, ForecastPeriod
from wxbench.providers import (
    fetch_accuweather_daily_forecast,
    fetch_accuweather_hourly_forecast,
    fetch_accuweather_location,
    fetch_accuweather_observation,
    fetch_ambient_weather_observation,
    fetch_msc_geomet_forecast,
    fetch_msc_geomet_observation,
    fetch_msc_rdps_prognos_forecast,
    rdps_prognos_endpoint,
    fetch_openweather_observation,
    fetch_openweather_onecall_daily,
    fetch_openweather_onecall_hourly,
    fetch_tomorrow_io_daily_forecast,
    fetch_tomorrow_io_forecast,
    fetch_tomorrow_io_observation,
)
from wxbench.providers.capture import CapturedPayload
from wxbench.storage.sqlite import RawPayload, ensure_schema, insert_data_points, insert_raw_payload, open_database


Clock = Callable[[], datetime]


@dataclass(frozen=True)
class CollectionResult:
    run_at: datetime
    raw_payloads: int
    data_points: int
    errors: tuple[str, ...]


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _to_raw_payload(captured: CapturedPayload) -> RawPayload:
    return RawPayload(
        provider=captured.provider,
        endpoint=captured.endpoint,
        run_at=captured.run_at,
        request_url=captured.request_url,
        request_params=captured.request_params,
        request_headers=captured.request_headers,
        response_status=captured.response_status,
        response_headers=captured.response_headers,
        payload_json=captured.payload_text,
    )


def collect_all(
    config: WxConfig,
    *,
    db_path: Optional[Path] = None,
    client: Optional[httpx.Client] = None,
    clock: Optional[Clock] = None,
    msc_rdps_max_lead_hours: Optional[int] = None,
) -> CollectionResult:
    """Fetch observations + hourly/daily forecasts from all providers."""

    run_at = (clock or _default_clock)()
    if run_at.tzinfo is None:
        run_at = run_at.replace(tzinfo=timezone.utc)

    connection = open_database(db_path)
    ensure_schema(connection)

    raw_count = 0
    point_count = 0
    errors: list[str] = []

    session = client or httpx.Client()
    close_client = client is None

    def _capture(holder: dict[str, int]) -> Callable[[CapturedPayload], None]:
        def _store(captured: CapturedPayload) -> None:
            nonlocal raw_count
            raw_id = insert_raw_payload(connection, _to_raw_payload(captured))
            holder["raw_id"] = raw_id
            raw_count += 1
        return _store

    try:
        # Ambient Weather (observation only)
        try:
            ambient_key = config.provider_keys.get("WX_AMBIENT_API_KEY")
            ambient_app = config.provider_keys.get("WX_AMBIENT_APPLICATION_KEY")
            ambient_device_mac = config.provider_keys.get("WX_AMBIENT_DEVICE_MAC")
            if ambient_key and ambient_app:
                holder: dict[str, int] = {}
                observation = fetch_ambient_weather_observation(
                    api_key=ambient_key,
                    application_key=ambient_app,
                    client=session,
                    device_mac=ambient_device_mac,
                    capture=_capture(holder),
                )
                raw_id = holder.get("raw_id")
                if raw_id:
                    points = observation_to_datapoints(observation, run_at=run_at, tz_name=config.timezone)
                    insert_data_points(connection, raw_id, points)
                    point_count += len(points)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"ambient_weather: {exc}")

        # MSC GeoMet
        try:
            holder: dict[str, int] = {}
            observation = fetch_msc_geomet_observation(
                latitude=config.latitude,
                longitude=config.longitude,
                client=session,
                capture=_capture(holder),
            )
            raw_id = holder.get("raw_id")
            if raw_id:
                points = observation_to_datapoints(observation, run_at=run_at, tz_name=config.timezone)
                insert_data_points(connection, raw_id, points)
                point_count += len(points)

            holder = {}
            forecast_periods = fetch_msc_geomet_forecast(
                latitude=config.latitude,
                longitude=config.longitude,
                client=session,
                capture=_capture(holder),
            )
            raw_id = holder.get("raw_id")
            if raw_id:
                hourly_points = _forecast_points(
                    forecast_periods,
                    run_at=run_at,
                    tz_name=config.timezone,
                    product_kind=PRODUCT_FORECAST_HOURLY,
                )
                insert_data_points(connection, raw_id, hourly_points)
                point_count += len(hourly_points)

                daily_periods = aggregate_daily_from_periods(forecast_periods, tz_name=config.timezone)
                daily_points = _forecast_points(
                    daily_periods,
                    run_at=run_at,
                    tz_name=config.timezone,
                    product_kind=PRODUCT_FORECAST_DAILY,
                    quality_flag="derived_daily_from_periods",
                )
                insert_data_points(connection, raw_id, daily_points)
                point_count += len(daily_points)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"msc_geomet: {exc}")

        # MSC RDPS PROGNOS (hourly station-point forecasts)
        try:
            rdps_raw_ids: dict[str, int] = {}

            def _capture_rdps(captured: CapturedPayload) -> None:
                nonlocal raw_count
                raw_id = insert_raw_payload(connection, _to_raw_payload(captured))
                rdps_raw_ids[captured.endpoint] = raw_id
                raw_count += 1

            rdps_periods = fetch_msc_rdps_prognos_forecast(
                latitude=config.latitude,
                longitude=config.longitude,
                client=session,
                max_lead_hours=84 if msc_rdps_max_lead_hours is None else msc_rdps_max_lead_hours,
                capture=_capture_rdps,
            )
            hourly_points = []
            for period in rdps_periods:
                lead_hours = int((period.start_time - period.issued_at).total_seconds() // 3600)
                endpoint = rdps_prognos_endpoint(period.issued_at, lead_hours, "AirTemp")
                raw_id = rdps_raw_ids.get(endpoint)
                if raw_id is None:
                    continue
                points = forecast_to_datapoints(
                    period,
                    run_at=run_at,
                    tz_name=config.timezone,
                    product_kind=PRODUCT_FORECAST_HOURLY,
                )
                insert_data_points(connection, raw_id, points)
                hourly_points.extend(points)
            point_count += len(hourly_points)

            daily_periods = aggregate_daily_from_periods(rdps_periods, tz_name=config.timezone)
            daily_points = _forecast_points(
                daily_periods,
                run_at=run_at,
                tz_name=config.timezone,
                product_kind=PRODUCT_FORECAST_DAILY,
                quality_flag="derived_daily_from_hourly",
            )
            if rdps_raw_ids and daily_points:
                anchor_raw_id = None
                if rdps_periods:
                    anchor_key = rdps_prognos_endpoint(rdps_periods[0].issued_at, 0, "AirTemp")
                    anchor_raw_id = rdps_raw_ids.get(anchor_key)
                if anchor_raw_id is None:
                    anchor_raw_id = next(iter(rdps_raw_ids.values()))
                insert_data_points(connection, anchor_raw_id, daily_points)
                point_count += len(daily_points)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"msc_rdps_prognos: {exc}")

        # OpenWeather
        try:
            openweather_key = config.provider_keys.get("WX_OPENWEATHER_API_KEY")
            if openweather_key:
                holder = {}
                observation = fetch_openweather_observation(
                    latitude=config.latitude,
                    longitude=config.longitude,
                    api_key=openweather_key,
                    client=session,
                    capture=_capture(holder),
                )
                raw_id = holder.get("raw_id")
                if raw_id:
                    points = observation_to_datapoints(observation, run_at=run_at, tz_name=config.timezone)
                    insert_data_points(connection, raw_id, points)
                    point_count += len(points)

                holder = {}
                hourly_periods = fetch_openweather_onecall_hourly(
                    latitude=config.latitude,
                    longitude=config.longitude,
                    api_key=openweather_key,
                    client=session,
                    capture=_capture(holder),
                )
                raw_id = holder.get("raw_id")
                if raw_id:
                    hourly_points = _forecast_points(
                        hourly_periods,
                        run_at=run_at,
                        tz_name=config.timezone,
                        product_kind=PRODUCT_FORECAST_HOURLY,
                    )
                    insert_data_points(connection, raw_id, hourly_points)
                    point_count += len(hourly_points)

                holder = {}
                daily_periods = fetch_openweather_onecall_daily(
                    latitude=config.latitude,
                    longitude=config.longitude,
                    api_key=openweather_key,
                    client=session,
                    capture=_capture(holder),
                )
                raw_id = holder.get("raw_id")
                if raw_id:
                    daily_points = _forecast_points(
                        daily_periods,
                        run_at=run_at,
                        tz_name=config.timezone,
                        product_kind=PRODUCT_FORECAST_DAILY,
                    )
                    insert_data_points(connection, raw_id, daily_points)
                    point_count += len(daily_points)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"openweather: {exc}")

        # Tomorrow.io
        try:
            tomorrow_key = config.provider_keys.get("WX_TOMORROW_IO_API_KEY")
            if tomorrow_key:
                holder = {}
                observation = fetch_tomorrow_io_observation(
                    latitude=config.latitude,
                    longitude=config.longitude,
                    api_key=tomorrow_key,
                    client=session,
                    capture=_capture(holder),
                )
                raw_id = holder.get("raw_id")
                if raw_id:
                    points = observation_to_datapoints(observation, run_at=run_at, tz_name=config.timezone)
                    insert_data_points(connection, raw_id, points)
                    point_count += len(points)

                holder = {}
                hourly_periods = fetch_tomorrow_io_forecast(
                    latitude=config.latitude,
                    longitude=config.longitude,
                    api_key=tomorrow_key,
                    client=session,
                    capture=_capture(holder),
                )
                raw_id = holder.get("raw_id")
                if raw_id:
                    hourly_points = _forecast_points(
                        hourly_periods,
                        run_at=run_at,
                        tz_name=config.timezone,
                        product_kind=PRODUCT_FORECAST_HOURLY,
                    )
                    insert_data_points(connection, raw_id, hourly_points)
                    point_count += len(hourly_points)

                holder = {}
                daily_periods = fetch_tomorrow_io_daily_forecast(
                    latitude=config.latitude,
                    longitude=config.longitude,
                    api_key=tomorrow_key,
                    client=session,
                    capture=_capture(holder),
                )
                raw_id = holder.get("raw_id")
                if raw_id:
                    daily_points = _forecast_points(
                        daily_periods,
                        run_at=run_at,
                        tz_name=config.timezone,
                        product_kind=PRODUCT_FORECAST_DAILY,
                    )
                    insert_data_points(connection, raw_id, daily_points)
                    point_count += len(daily_points)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"tomorrow_io: {exc}")

        # AccuWeather
        try:
            accuweather_key = config.provider_keys.get("WX_ACCUWEATHER_API_KEY")
            if accuweather_key:
                holder = {}
                location = fetch_accuweather_location(
                    latitude=config.latitude,
                    longitude=config.longitude,
                    api_key=accuweather_key,
                    client=session,
                    capture=_capture(holder),
                )
                location_key = location.key

                holder = {}
                observation = fetch_accuweather_observation(
                    location_key=location_key,
                    latitude=config.latitude,
                    longitude=config.longitude,
                    api_key=accuweather_key,
                    client=session,
                    capture=_capture(holder),
                )
                raw_id = holder.get("raw_id")
                if raw_id:
                    points = observation_to_datapoints(observation, run_at=run_at, tz_name=config.timezone)
                    insert_data_points(connection, raw_id, points)
                    point_count += len(points)

                holder = {}
                hourly_periods = fetch_accuweather_hourly_forecast(
                    location_key=location_key,
                    latitude=config.latitude,
                    longitude=config.longitude,
                    api_key=accuweather_key,
                    client=session,
                    capture=_capture(holder),
                )
                raw_id = holder.get("raw_id")
                if raw_id:
                    hourly_points = _forecast_points(
                        hourly_periods,
                        run_at=run_at,
                        tz_name=config.timezone,
                        product_kind=PRODUCT_FORECAST_HOURLY,
                    )
                    insert_data_points(connection, raw_id, hourly_points)
                    point_count += len(hourly_points)

                holder = {}
                daily_periods = fetch_accuweather_daily_forecast(
                    location_key=location_key,
                    latitude=config.latitude,
                    longitude=config.longitude,
                    api_key=accuweather_key,
                    client=session,
                    capture=_capture(holder),
                )
                raw_id = holder.get("raw_id")
                if raw_id:
                    daily_points = _forecast_points(
                        daily_periods,
                        run_at=run_at,
                        tz_name=config.timezone,
                        product_kind=PRODUCT_FORECAST_DAILY,
                    )
                    insert_data_points(connection, raw_id, daily_points)
                    point_count += len(daily_points)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"accuweather: {exc}")

        connection.commit()
    finally:
        if close_client:
            session.close()
        connection.close()

    return CollectionResult(run_at=run_at, raw_payloads=raw_count, data_points=point_count, errors=tuple(errors))


def _forecast_points(
    periods: Iterable[ForecastPeriod],
    *,
    run_at: datetime,
    tz_name: str,
    product_kind: str,
    quality_flag: Optional[str] = None,
) -> list[DataPoint]:
    points: list[DataPoint] = []
    if product_kind == PRODUCT_FORECAST_DAILY:
        for index, period in enumerate(periods):
            points.extend(
                forecast_to_datapoints(
                    period,
                    run_at=run_at,
                    tz_name=tz_name,
                    product_kind=product_kind,
                    lead_day_index=index,
                    quality_flag=quality_flag,
                )
            )
    else:
        for period in periods:
            points.extend(
                forecast_to_datapoints(
                    period,
                    run_at=run_at,
                    tz_name=tz_name,
                    product_kind=product_kind,
                    quality_flag=quality_flag,
                )
            )
    return points


__all__ = ["CollectionResult", "collect_all"]
