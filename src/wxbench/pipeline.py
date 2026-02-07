"""Orchestration for fetching provider data and storing normalized points."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import time
from pathlib import Path
from typing import Callable, Iterable, Optional

import httpx

from wxbench.config import WxConfig
from wxbench.domain.aggregate import aggregate_daily_from_periods
from wxbench.domain.datapoints import (
    PRODUCT_FORECAST_MINUTELY,
    PRODUCT_FORECAST_DAILY,
    PRODUCT_FORECAST_HOURLY,
    alerts_to_datapoints,
    observation_to_datapoints,
    forecast_to_datapoints,
)
from wxbench.domain.models import DataPoint, ForecastPeriod, Location
from wxbench.providers import (
    fetch_accuweather_daily_forecast,
    fetch_accuweather_hourly_forecast,
    fetch_accuweather_location,
    fetch_accuweather_observation,
    fetch_ambient_weather_observation,
    fetch_ecowitt_observation,
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
    fetch_weatherkit_bundle,
)
from wxbench.providers.capture import CapturedPayload
from wxbench.providers.errors import ProviderError
from wxbench.storage.datapoints import DataPointWriterFactory
from wxbench.storage.sqlite import RawPayload, ensure_schema, insert_raw_payload, open_database


Clock = Callable[[], datetime]
EventLogger = Callable[[dict[str, object]], None]


@dataclass(frozen=True)
class CollectionResult:
    run_at: datetime
    raw_payloads: int
    data_points: int
    errors: tuple[str, ...]


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _to_raw_payload(captured: CapturedPayload, *, run_at: datetime) -> RawPayload:
    return RawPayload(
        provider=captured.provider,
        endpoint=captured.endpoint,
        run_at=run_at,
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
    msc_rdps_max_lead_hours: int = 24,
    data_point_writer_factory: DataPointWriterFactory,
    event_logger: Optional[EventLogger] = None,
) -> CollectionResult:
    """Fetch observations + hourly/daily forecasts from all providers."""

    run_at = (clock or _default_clock)()
    if run_at.tzinfo is None:
        run_at = run_at.replace(tzinfo=timezone.utc)

    connection = open_database(db_path)
    ensure_schema(connection)
    data_point_writer = data_point_writer_factory(connection)

    raw_count = 0
    point_count = 0
    errors: list[str] = []

    session = client or httpx.Client(timeout=httpx.Timeout(30.0))
    close_client = client is None

    def _emit(event: dict[str, object]) -> None:
        if event_logger is not None:
            event_logger(event)

    def _capture(holder: dict[str, int]) -> Callable[[CapturedPayload], None]:
        def _store(captured: CapturedPayload) -> None:
            nonlocal raw_count
            raw_id = insert_raw_payload(connection, _to_raw_payload(captured, run_at=run_at))
            holder["raw_id"] = raw_id
            raw_count += 1
        return _store

    def _store_points(raw_id: int, points: Iterable[DataPoint]) -> int:
        return data_point_writer.write(raw_id, points, run_at=run_at)

    try:
        # EcoWitt (observation only; preferred station ground truth)
        try:
            ecowitt_key = config.provider_keys.get("WX_ECOWITT_API_KEY")
            ecowitt_app = config.provider_keys.get("WX_ECOWITT_APPLICATION_KEY")
            ecowitt_device_mac = config.provider_keys.get("WX_ECOWITT_DEVICE_MAC")
            ecowitt_station = config.provider_keys.get("WX_ECOWITT_STATION")
            if ecowitt_key and ecowitt_app and ecowitt_device_mac:
                provider_start = time.monotonic()
                raw_before = raw_count
                point_before = point_count
                _emit({"event": "provider_start", "provider": "ecowitt"})
                holder: dict[str, int] = {}
                observation = fetch_ecowitt_observation(
                    api_key=ecowitt_key,
                    application_key=ecowitt_app,
                    device_mac=ecowitt_device_mac,
                    location=Location(latitude=config.latitude, longitude=config.longitude),
                    station=ecowitt_station or ecowitt_device_mac,
                    client=session,
                    capture=_capture(holder),
                )
                raw_id = holder.get("raw_id")
                if raw_id:
                    points = observation_to_datapoints(observation, run_at=run_at, tz_name=config.timezone)
                    point_count += _store_points(raw_id, points)
                _emit(
                    {
                        "event": "provider_success",
                        "provider": "ecowitt",
                        "raw_payloads": raw_count - raw_before,
                        "data_points": point_count - point_before,
                        "duration_seconds": time.monotonic() - provider_start,
                    }
                )
            else:
                reason = "missing_keys"
                if ecowitt_key and ecowitt_app and not ecowitt_device_mac:
                    reason = "missing_device_mac"
                _emit({"event": "provider_skip", "provider": "ecowitt", "reason": reason})
        except ProviderError as exc:
            errors.append(str(exc))
            _emit(
                {
                    "event": "provider_error",
                    "provider": "ecowitt",
                    "operation": exc.operation,
                    "error_type": exc.__class__.__name__,
                    "message": exc.message,
                }
            )
            connection.commit()
        else:
            connection.commit()

        # Ambient Weather (observation only)
        try:
            ambient_key = config.provider_keys.get("WX_AMBIENT_API_KEY")
            ambient_app = config.provider_keys.get("WX_AMBIENT_APPLICATION_KEY")
            ambient_device_mac = config.provider_keys.get("WX_AMBIENT_DEVICE_MAC")
            if ambient_key and ambient_app:
                provider_start = time.monotonic()
                raw_before = raw_count
                point_before = point_count
                _emit({"event": "provider_start", "provider": "ambient_weather"})
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
                    point_count += _store_points(raw_id, points)
                _emit(
                    {
                        "event": "provider_success",
                        "provider": "ambient_weather",
                        "raw_payloads": raw_count - raw_before,
                        "data_points": point_count - point_before,
                        "duration_seconds": time.monotonic() - provider_start,
                    }
                )
            else:
                _emit({"event": "provider_skip", "provider": "ambient_weather", "reason": "missing_keys"})
        except ProviderError as exc:
            errors.append(str(exc))
            _emit(
                {
                    "event": "provider_error",
                    "provider": "ambient_weather",
                    "operation": exc.operation,
                    "error_type": exc.__class__.__name__,
                    "message": exc.message,
                }
            )
            connection.commit()
        else:
            connection.commit()

        # MSC GeoMet
        try:
            provider_start = time.monotonic()
            raw_before = raw_count
            point_before = point_count
            _emit({"event": "provider_start", "provider": "msc_geomet"})
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
                point_count += _store_points(raw_id, points)

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
                point_count += _store_points(raw_id, hourly_points)

                daily_periods = aggregate_daily_from_periods(forecast_periods, tz_name=config.timezone)
                daily_points = _forecast_points(
                    daily_periods,
                    run_at=run_at,
                    tz_name=config.timezone,
                    product_kind=PRODUCT_FORECAST_DAILY,
                    quality_flag="derived_daily_from_periods",
                )
                point_count += _store_points(raw_id, daily_points)
            _emit(
                {
                    "event": "provider_success",
                    "provider": "msc_geomet",
                    "raw_payloads": raw_count - raw_before,
                    "data_points": point_count - point_before,
                    "duration_seconds": time.monotonic() - provider_start,
                }
            )
        except ProviderError as exc:
            errors.append(str(exc))
            _emit(
                {
                    "event": "provider_error",
                    "provider": "msc_geomet",
                    "operation": exc.operation,
                    "error_type": exc.__class__.__name__,
                    "message": exc.message,
                }
            )
            connection.commit()
        else:
            connection.commit()

        # MSC RDPS PROGNOS (hourly station-point forecasts)
        try:
            provider_start = time.monotonic()
            raw_before = raw_count
            point_before = point_count
            _emit({"event": "provider_start", "provider": "msc_rdps_prognos"})
            rdps_raw_ids: dict[str, int] = {}

            def _capture_rdps(captured: CapturedPayload) -> None:
                nonlocal raw_count
                raw_id = insert_raw_payload(connection, _to_raw_payload(captured, run_at=run_at))
                rdps_raw_ids[captured.endpoint] = raw_id
                raw_count += 1

            rdps_periods = fetch_msc_rdps_prognos_forecast(
                latitude=config.latitude,
                longitude=config.longitude,
                client=session,
                max_lead_hours=msc_rdps_max_lead_hours,
                run_time=run_at,
                capture=_capture_rdps,
            )
            hourly_count = 0
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
                hourly_count += _store_points(raw_id, points)
            point_count += hourly_count

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
                point_count += _store_points(anchor_raw_id, daily_points)
            _emit(
                {
                    "event": "provider_success",
                    "provider": "msc_rdps_prognos",
                    "raw_payloads": raw_count - raw_before,
                    "data_points": point_count - point_before,
                    "duration_seconds": time.monotonic() - provider_start,
                }
            )
        except ProviderError as exc:
            errors.append(str(exc))
            _emit(
                {
                    "event": "provider_error",
                    "provider": "msc_rdps_prognos",
                    "operation": exc.operation,
                    "error_type": exc.__class__.__name__,
                    "message": exc.message,
                }
            )
            connection.commit()
        else:
            connection.commit()

        # OpenWeather
        try:
            openweather_key = config.provider_keys.get("WX_OPENWEATHER_API_KEY")
            if openweather_key:
                provider_start = time.monotonic()
                raw_before = raw_count
                point_before = point_count
                _emit({"event": "provider_start", "provider": "openweather"})
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
                    point_count += _store_points(raw_id, points)

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
                    point_count += _store_points(raw_id, hourly_points)

                    derived_daily = aggregate_daily_from_periods(hourly_periods, tz_name=config.timezone)
                    if derived_daily:
                        derived_points = _forecast_points(
                            derived_daily,
                            run_at=run_at,
                            tz_name=config.timezone,
                            product_kind=PRODUCT_FORECAST_DAILY,
                            quality_flag="derived_daily_from_hourly",
                        )
                        point_count += _store_points(raw_id, derived_points)

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
                    point_count += _store_points(raw_id, daily_points)
                _emit(
                    {
                        "event": "provider_success",
                        "provider": "openweather",
                        "raw_payloads": raw_count - raw_before,
                        "data_points": point_count - point_before,
                        "duration_seconds": time.monotonic() - provider_start,
                    }
                )
            else:
                _emit({"event": "provider_skip", "provider": "openweather", "reason": "missing_keys"})
        except ProviderError as exc:
            errors.append(str(exc))
            _emit(
                {
                    "event": "provider_error",
                    "provider": "openweather",
                    "operation": exc.operation,
                    "error_type": exc.__class__.__name__,
                    "message": exc.message,
                }
            )
            connection.commit()
        else:
            connection.commit()

        # Tomorrow.io
        try:
            tomorrow_key = config.provider_keys.get("WX_TOMORROW_IO_API_KEY")
            if tomorrow_key:
                provider_start = time.monotonic()
                raw_before = raw_count
                point_before = point_count
                _emit({"event": "provider_start", "provider": "tomorrow_io"})
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
                    point_count += _store_points(raw_id, points)

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
                    point_count += _store_points(raw_id, hourly_points)

                    derived_daily = aggregate_daily_from_periods(hourly_periods, tz_name=config.timezone)
                    if derived_daily:
                        derived_points = _forecast_points(
                            derived_daily,
                            run_at=run_at,
                            tz_name=config.timezone,
                            product_kind=PRODUCT_FORECAST_DAILY,
                            quality_flag="derived_daily_from_hourly",
                        )
                        point_count += _store_points(raw_id, derived_points)

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
                    point_count += _store_points(raw_id, daily_points)
                _emit(
                    {
                        "event": "provider_success",
                        "provider": "tomorrow_io",
                        "raw_payloads": raw_count - raw_before,
                        "data_points": point_count - point_before,
                        "duration_seconds": time.monotonic() - provider_start,
                    }
                )
            else:
                _emit({"event": "provider_skip", "provider": "tomorrow_io", "reason": "missing_keys"})
        except ProviderError as exc:
            errors.append(str(exc))
            _emit(
                {
                    "event": "provider_error",
                    "provider": "tomorrow_io",
                    "operation": exc.operation,
                    "error_type": exc.__class__.__name__,
                    "message": exc.message,
                }
            )
            connection.commit()
        else:
            connection.commit()

        # WeatherKit
        try:
            weatherkit_team_id = config.provider_keys.get("WX_WEATHERKIT_TEAM_ID")
            weatherkit_service_id = config.provider_keys.get("WX_WEATHERKIT_SERVICE_ID")
            weatherkit_key_id = config.provider_keys.get("WX_WEATHERKIT_KEY_ID")
            weatherkit_key_path = config.provider_keys.get("WX_WEATHERKIT_KEY_PATH")
            weatherkit_country_code = config.provider_keys.get("WX_WEATHERKIT_COUNTRY_CODE")
            if weatherkit_team_id and weatherkit_service_id and weatherkit_key_id and weatherkit_key_path:
                provider_start = time.monotonic()
                raw_before = raw_count
                point_before = point_count
                _emit({"event": "provider_start", "provider": "weatherkit"})
                holder: dict[str, int] = {}
                bundle = fetch_weatherkit_bundle(
                    latitude=config.latitude,
                    longitude=config.longitude,
                    timezone_name=config.timezone,
                    country_code=weatherkit_country_code,
                    client=session,
                    team_id=weatherkit_team_id,
                    service_id=weatherkit_service_id,
                    key_id=weatherkit_key_id,
                    key_path=weatherkit_key_path,
                    capture=_capture(holder),
                )
                raw_id = holder.get("raw_id")
                if raw_id:
                    if bundle.observation is not None:
                        points = observation_to_datapoints(bundle.observation, run_at=run_at, tz_name=config.timezone)
                        point_count += _store_points(raw_id, points)

                    if bundle.hourly:
                        hourly_points = _forecast_points(
                            bundle.hourly,
                            run_at=run_at,
                            tz_name=config.timezone,
                            product_kind=PRODUCT_FORECAST_HOURLY,
                        )
                        point_count += _store_points(raw_id, hourly_points)

                        derived_daily = aggregate_daily_from_periods(bundle.hourly, tz_name=config.timezone)
                        if derived_daily:
                            derived_points = _forecast_points(
                                derived_daily,
                                run_at=run_at,
                                tz_name=config.timezone,
                                product_kind=PRODUCT_FORECAST_DAILY,
                                quality_flag="derived_daily_from_hourly",
                            )
                            point_count += _store_points(raw_id, derived_points)

                    if bundle.daily:
                        daily_points = _forecast_points(
                            bundle.daily,
                            run_at=run_at,
                            tz_name=config.timezone,
                            product_kind=PRODUCT_FORECAST_DAILY,
                        )
                        point_count += _store_points(raw_id, daily_points)

                    if bundle.next_hour:
                        minute_points = _forecast_points(
                            bundle.next_hour,
                            run_at=run_at,
                            tz_name=config.timezone,
                            product_kind=PRODUCT_FORECAST_MINUTELY,
                        )
                        point_count += _store_points(raw_id, minute_points)

                    if bundle.alerts:
                        alert_points: list[DataPoint] = []
                        for alert in bundle.alerts:
                            alert_points.extend(
                                alerts_to_datapoints(alert, run_at=run_at, tz_name=config.timezone)
                            )
                        point_count += _store_points(raw_id, alert_points)
                _emit(
                    {
                        "event": "provider_success",
                        "provider": "weatherkit",
                        "raw_payloads": raw_count - raw_before,
                        "data_points": point_count - point_before,
                        "duration_seconds": time.monotonic() - provider_start,
                    }
                )
            else:
                _emit({"event": "provider_skip", "provider": "weatherkit", "reason": "missing_keys"})
        except ProviderError as exc:
            errors.append(str(exc))
            _emit(
                {
                    "event": "provider_error",
                    "provider": "weatherkit",
                    "operation": exc.operation,
                    "error_type": exc.__class__.__name__,
                    "message": exc.message,
                }
            )
            connection.commit()
        else:
            connection.commit()

        # AccuWeather
        try:
            accuweather_key = config.provider_keys.get("WX_ACCUWEATHER_API_KEY")
            if accuweather_key:
                provider_start = time.monotonic()
                raw_before = raw_count
                point_before = point_count
                _emit({"event": "provider_start", "provider": "accuweather"})
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
                    point_count += _store_points(raw_id, points)

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
                    point_count += _store_points(raw_id, hourly_points)

                    derived_daily = aggregate_daily_from_periods(hourly_periods, tz_name=config.timezone)
                    if derived_daily:
                        derived_points = _forecast_points(
                            derived_daily,
                            run_at=run_at,
                            tz_name=config.timezone,
                            product_kind=PRODUCT_FORECAST_DAILY,
                            quality_flag="derived_daily_from_hourly",
                        )
                        point_count += _store_points(raw_id, derived_points)

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
                    point_count += _store_points(raw_id, daily_points)
                _emit(
                    {
                        "event": "provider_success",
                        "provider": "accuweather",
                        "raw_payloads": raw_count - raw_before,
                        "data_points": point_count - point_before,
                        "duration_seconds": time.monotonic() - provider_start,
                    }
                )
            else:
                _emit({"event": "provider_skip", "provider": "accuweather", "reason": "missing_keys"})
        except ProviderError as exc:
            errors.append(str(exc))
            _emit(
                {
                    "event": "provider_error",
                    "provider": "accuweather",
                    "operation": exc.operation,
                    "error_type": exc.__class__.__name__,
                    "message": exc.message,
                }
            )
            connection.commit()
        else:
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
