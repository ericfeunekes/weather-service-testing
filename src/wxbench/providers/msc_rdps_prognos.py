"""Adapter for MSC RDPS PROGNOS station-point forecasts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import httpx
from pydantic import ValidationError

from wxbench.domain.mappers.msc_rdps_prognos import (
    PrognosStationValue,
    parse_prognos_payload,
    select_nearest_station,
    value_for_station,
)
from wxbench.domain.models import ForecastPeriod, Location
from wxbench.providers._http import DEFAULT_TIMEOUT, send_with_retries
from wxbench.providers.capture import CapturedPayload, capture_payload
from wxbench.providers.errors import ProviderPayloadError, ProviderRequestError
from wxbench.providers.schemas import RdpsPrognosFeatureCollectionPayload

__all__ = ["fetch_msc_rdps_prognos_forecast", "rdps_prognos_endpoint"]


BASE_URL = "https://dd.weather.gc.ca/today/model_rdps/stat-post-processing"
RUN_CYCLES = (0, 6, 12, 18)


@dataclass(frozen=True)
class _VariableSpec:
    name: str
    method: str
    vertical: str
    forecast_attr: str


_VARIABLES = (
    _VariableSpec("AirTemp", "MLR", "AGL-1.5m", "temperature_c"),
    _VariableSpec("DewPoint", "MLR", "AGL-1.5m", "dewpoint_c"),
    _VariableSpec("WindSpeed", "LASSO", "AGL-10m", "wind_speed_kph"),
    _VariableSpec("WindDir", "WDLASSO2", "AGL-10m", "wind_direction_deg"),
)


def _select_run_time(now: datetime) -> datetime:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    current_hour = now.hour
    for hour in reversed(RUN_CYCLES):
        if current_hour >= hour:
            return now.replace(hour=hour, minute=0, second=0, microsecond=0)
    previous_day = (now - timedelta(days=1)).date()
    return datetime(previous_day.year, previous_day.month, previous_day.day, 18, tzinfo=timezone.utc)


def _build_filename(run_time: datetime, lead_hour: int, spec: _VariableSpec) -> str:
    stamp = run_time.strftime("%Y%m%dT%HZ")
    lead = f"{lead_hour:03d}"
    return f"{stamp}_MSC_RDPS-PROGNOS-{spec.method}-{spec.name}_{spec.vertical}_PT{lead}H.json"


def _build_url(base_url: str, run_time: datetime, lead_hour: int, spec: _VariableSpec) -> str:
    return f"{base_url}/{run_time:%H}/{lead_hour:03d}/{_build_filename(run_time, lead_hour, spec)}"


def rdps_prognos_endpoint(run_time: datetime, lead_hour: int, variable: str) -> str:
    return f"rdps_prognos_{run_time:%Y%m%dT%HZ}_lead{lead_hour:03d}_{variable.lower()}"


def _resolve_run_time(
    *,
    now: datetime,
    client: httpx.Client,
    base_url: str,
    timeout: httpx.Timeout | float | None,
    retries: int,
    capture: Optional[Callable[[CapturedPayload], None]],
) -> tuple[datetime, Optional[dict]]:
    run_time = _select_run_time(now)
    attempts = 0
    while attempts < len(RUN_CYCLES):
        lead_hour = 0
        spec = _VARIABLES[0]
        url = _build_url(base_url, run_time, lead_hour, spec)
        request = client.build_request("GET", url, headers={"accept": "application/geo+json"}, timeout=timeout)
        try:
            response = send_with_retries(
                client,
                request,
                provider="msc_rdps_prognos",
                operation="forecast_check",
                retries=retries,
            )
        except ProviderRequestError:
            attempts += 1
            run_time -= timedelta(hours=6)
            continue

        payload_text = response.text
        if capture is not None:
            capture(
                capture_payload(
                    provider="msc_rdps_prognos",
                    endpoint=rdps_prognos_endpoint(run_time, lead_hour, spec.name),
                    run_at=datetime.now(timezone.utc),
                    request=request,
                    response=response,
                    payload_text=payload_text,
                )
            )

        try:
            payload = response.json()
        except (ValueError, httpx.HTTPError) as exc:
            raise ProviderPayloadError("msc_rdps_prognos", "forecast", "Invalid JSON payload") from exc
        try:
            RdpsPrognosFeatureCollectionPayload.model_validate(payload)
        except ValidationError as exc:
            raise ProviderPayloadError("msc_rdps_prognos", "forecast", "Unexpected payload shape") from exc

        return run_time, payload

    raise ProviderRequestError("msc_rdps_prognos", "forecast", "No available RDPS PROGNOS run found")


def _convert_value(value: PrognosStationValue, spec: _VariableSpec) -> Optional[float]:
    unit = value.unit
    if spec.name in ("AirTemp", "DewPoint"):
        if unit.upper() == "K":
            return value.value - 273.15
        return value.value
    if spec.name == "WindSpeed":
        return value.value
    if spec.name == "WindDir":
        return float(int(round(value.value)))
    return None


def fetch_msc_rdps_prognos_forecast(
    *,
    latitude: float,
    longitude: float,
    client: httpx.Client,
    base_url: str = BASE_URL,
    max_lead_hours: int = 84,
    run_time: Optional[datetime] = None,
    retries: int = 2,
    timeout: Optional[httpx.Timeout] | float | None = DEFAULT_TIMEOUT,
    capture: Optional[Callable[[CapturedPayload], None]] = None,
) -> list[ForecastPeriod]:
    """Fetch RDPS PROGNOS station forecasts and map to hourly periods."""

    now = run_time or datetime.now(timezone.utc)
    run_reference_time, cached_payload = _resolve_run_time(
        now=now, client=client, base_url=base_url, timeout=timeout, retries=retries, capture=capture
    )

    station_id: Optional[str] = None
    station_lat = station_lon = None

    periods: list[ForecastPeriod] = []
    cached_used = False
    for lead_hour in range(0, max_lead_hours + 1):
        values_by_attr: dict[str, Optional[float]] = {}
        forecast_time: Optional[datetime] = None
        issued_at: Optional[datetime] = None

        for spec in _VARIABLES:
            if lead_hour == 0 and spec == _VARIABLES[0] and cached_payload and not cached_used:
                payload = cached_payload
                cached_used = True
            else:
                url = _build_url(base_url, run_reference_time, lead_hour, spec)
                request = client.build_request("GET", url, headers={"accept": "application/geo+json"}, timeout=timeout)
                response = send_with_retries(
                    client,
                    request,
                    provider="msc_rdps_prognos",
                    operation="forecast",
                    retries=retries,
                )
                payload_text = response.text
                if capture is not None:
                    capture(
                        capture_payload(
                            provider="msc_rdps_prognos",
                            endpoint=rdps_prognos_endpoint(run_reference_time, lead_hour, spec.name),
                            run_at=datetime.now(timezone.utc),
                            request=request,
                            response=response,
                            payload_text=payload_text,
                        )
                    )
                try:
                    payload = response.json()
                except (ValueError, httpx.HTTPError) as exc:
                    raise ProviderPayloadError("msc_rdps_prognos", "forecast", "Invalid JSON payload") from exc
                try:
                    RdpsPrognosFeatureCollectionPayload.model_validate(payload)
                except ValidationError as exc:
                    raise ProviderPayloadError("msc_rdps_prognos", "forecast", "Unexpected payload shape") from exc

            values = parse_prognos_payload(payload)

            if station_id is None:
                station_id, station_lat, station_lon = select_nearest_station(values, latitude, longitude)

            station_value = value_for_station(values, station_id)
            if station_value is None:
                station_value = values[0]

            converted_value = _convert_value(station_value, spec)
            values_by_attr[spec.forecast_attr] = converted_value
            forecast_time = station_value.forecast_time
            issued_at = station_value.reference_time

        if forecast_time is None or issued_at is None or station_lat is None or station_lon is None:
            continue

        start_time = forecast_time
        end_time = start_time + timedelta(hours=1)

        periods.append(
            ForecastPeriod(
                provider="msc_rdps_prognos",
                location=Location(latitude=float(station_lat), longitude=float(station_lon)),
                issued_at=issued_at,
                start_time=start_time,
                end_time=end_time,
                temperature_c=values_by_attr.get("temperature_c"),
                dewpoint_c=values_by_attr.get("dewpoint_c"),
                wind_speed_kph=values_by_attr.get("wind_speed_kph"),
                wind_direction_deg=int(values_by_attr["wind_direction_deg"]) if values_by_attr.get("wind_direction_deg") is not None else None,
            )
        )

    return periods
