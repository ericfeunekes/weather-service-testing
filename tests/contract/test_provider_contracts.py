from __future__ import annotations

import os
import re
from pathlib import Path

import httpx
import pytest
import vcr

from datetime import datetime, timedelta, timezone

from wxbench.providers import (
    fetch_accuweather_daily_forecast,
    fetch_accuweather_hourly_forecast,
    fetch_accuweather_location,
    fetch_accuweather_minute_forecast,
    fetch_accuweather_observation,
    fetch_ambient_weather_history,
    fetch_msc_geomet_forecast,
    fetch_msc_geomet_observation,
    fetch_msc_rdps_prognos_forecast,
    fetch_ambient_weather_observation,
    fetch_openweather_forecast,
    fetch_openweather_observation,
    fetch_openweather_onecall_daily,
    fetch_openweather_onecall_hourly,
    fetch_tomorrow_io_daily_forecast,
    fetch_tomorrow_io_forecast,
    fetch_tomorrow_io_observation,
)
from wxbench.providers.weatherkit import fetch_weatherkit_bundle


CASSETTE_DIR = Path(__file__).parent / "cassettes"

recorder = vcr.VCR(
    cassette_library_dir=str(CASSETTE_DIR),
    record_mode=os.getenv("WX_VCR_RECORD_MODE", "none"),
    filter_query_parameters=[
        ("appid", "REDACTED"),
        ("apikey", "REDACTED"),
        ("api_key", "REDACTED"),
        ("apiKey", "REDACTED"),
        ("applicationKey", "REDACTED"),
        ("application_key", "REDACTED"),
        ("mac", "REDACTED"),
    ],
    filter_headers=["authorization"],
    match_on=["method", "scheme", "host", "port", "path", "query"],
)


RECORDING = recorder.record_mode != "none"

DEFAULT_AMBIENT_API_KEY = "super-secret"
DEFAULT_AMBIENT_APPLICATION_KEY = "another-secret"
DEFAULT_ACCUWEATHER_API_KEY = "super-secret"
DEFAULT_OPENWEATHER_API_KEY = "super-secret"
DEFAULT_TOMORROW_IO_API_KEY = "another-secret"
DEFAULT_WEATHERKIT_TEAM_ID = "DEMO_TEAM_ID"
DEFAULT_WEATHERKIT_SERVICE_ID = "com.example.weatherkit"
DEFAULT_WEATHERKIT_KEY_ID = "DEMO_KEY_ID"


def _require_env(var: str, *, provider: str) -> str:
    value = os.getenv(var)
    if value:
        value = value.strip()
    if RECORDING and not value:
        pytest.skip(f"Set {var} to hit the live {provider} API")
    return value or ""


def _ambient_keys() -> tuple[str, str]:
    api_key = _require_env("WX_AMBIENT_API_KEY", provider="AmbientWeather") or DEFAULT_AMBIENT_API_KEY
    application_key = _require_env("WX_AMBIENT_APPLICATION_KEY", provider="AmbientWeather") or DEFAULT_AMBIENT_APPLICATION_KEY
    return api_key, application_key


def _ambient_device_mac() -> str | None:
    value = os.getenv("WX_AMBIENT_DEVICE_MAC")
    if RECORDING and value:
        return value.strip()
    return None


def _ambient_history_mac() -> str:
    value = os.getenv("WX_AMBIENT_DEVICE_MAC")
    if RECORDING:
        if value:
            return value.strip()
        pytest.skip("Set WX_AMBIENT_DEVICE_MAC to record Ambient history")
    cassette_path = CASSETTE_DIR / "ambient_weather_history.yaml"
    if cassette_path.exists():
        text = cassette_path.read_text()
        match = re.search(r"/v1/devices/([^?\\s]+)", text)
        if match:
            return match.group(1)
    return (value or "00:11:22:33:44:55").strip()


def _openweather_key() -> str:
    return _require_env("WX_OPENWEATHER_API_KEY", provider="OpenWeather") or DEFAULT_OPENWEATHER_API_KEY


def _accuweather_key() -> str:
    return _require_env("WX_ACCUWEATHER_API_KEY", provider="AccuWeather") or DEFAULT_ACCUWEATHER_API_KEY


def _tomorrow_io_key() -> str:
    return _require_env("WX_TOMORROW_IO_API_KEY", provider="Tomorrow.io") or DEFAULT_TOMORROW_IO_API_KEY


def _weatherkit_team_id() -> str:
    return _require_env("WX_WEATHERKIT_TEAM_ID", provider="WeatherKit") or DEFAULT_WEATHERKIT_TEAM_ID


def _weatherkit_service_id() -> str:
    return _require_env("WX_WEATHERKIT_SERVICE_ID", provider="WeatherKit") or DEFAULT_WEATHERKIT_SERVICE_ID


def _weatherkit_key_id() -> str:
    return _require_env("WX_WEATHERKIT_KEY_ID", provider="WeatherKit") or DEFAULT_WEATHERKIT_KEY_ID


def _weatherkit_key_path(tmp_path: Path) -> str:
    value = os.getenv("WX_WEATHERKIT_KEY_PATH")
    if value:
        return value
    if RECORDING:
        pytest.skip("Set WX_WEATHERKIT_KEY_PATH to record WeatherKit")

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    private_key = ec.generate_private_key(ec.SECP256R1())
    path = tmp_path / "weatherkit_key.p8"
    path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    return str(path)


def _coords(*, default_lat: float, default_lon: float) -> tuple[float, float]:
    lat_raw = os.getenv("WX_LAT")
    lon_raw = os.getenv("WX_LON")
    if lat_raw and lon_raw:
        try:
            return float(lat_raw), float(lon_raw)
        except ValueError:
            pytest.skip("Invalid coordinates provided via WX_LAT/WX_LON")
    return default_lat, default_lon


def _assert_period_sequence(
    periods,
    *,
    expected_step: timedelta | None = None,
    min_step: timedelta = timedelta(seconds=1),
) -> None:
    assert periods
    starts = [period.start_time for period in periods]
    assert starts == sorted(starts)
    assert all(period.end_time > period.start_time for period in periods)
    deltas = [next_start - start for start, next_start in zip(starts, starts[1:])]
    if not deltas:
        return
    assert all(delta >= min_step for delta in deltas)
    if expected_step is None:
        expected_step = deltas[0]
    expected_seconds = int(expected_step.total_seconds())
    assert expected_seconds > 0
    for delta in deltas:
        delta_seconds = int(delta.total_seconds())
        assert delta_seconds >= expected_seconds
        assert delta_seconds % expected_seconds == 0


@pytest.fixture()
def client() -> httpx.Client:
    with httpx.Client() as session:
        yield session


def test_ambient_weather_observation_contract(client: httpx.Client) -> None:
    with recorder.use_cassette("ambient_weather_observation.yaml"):
        api_key, application_key = _ambient_keys()
        observation = fetch_ambient_weather_observation(
            api_key=api_key,
            application_key=application_key,
            device_mac=_ambient_device_mac(),
            client=client,
        )

    assert observation.provider == "ambient_weather"
    assert observation.station
    assert observation.location.latitude is not None
    assert observation.location.longitude is not None
    assert observation.temperature_c is not None


def test_ambient_weather_history_contract(client: httpx.Client) -> None:
    with recorder.use_cassette("ambient_weather_history.yaml"):
        api_key, application_key = _ambient_keys()
        observation = fetch_ambient_weather_observation(
            api_key=api_key,
            application_key=application_key,
            device_mac=_ambient_device_mac(),
            client=client,
        )
        history = fetch_ambient_weather_history(
            api_key=api_key,
            application_key=application_key,
            device_mac=_ambient_history_mac(),
            location=observation.location,
            station=observation.station,
            end_at=datetime(2025, 12, 31, 12, tzinfo=timezone.utc),
            client=client,
        )

    assert history
    assert history[0].observed_at is not None


def test_accuweather_minute_forecast_contract(client: httpx.Client) -> None:
    with recorder.use_cassette("accuweather_minute_forecast.yaml"):
        latitude, longitude = _coords(default_lat=44.639, default_lon=-63.587)
        periods = fetch_accuweather_minute_forecast(
            latitude=latitude,
            longitude=longitude,
            api_key=_accuweather_key(),
            client=client,
        )

    assert periods
    assert periods[0].location.latitude == pytest.approx(latitude, abs=0.01)
    assert periods[0].location.longitude == pytest.approx(longitude, abs=0.01)
    assert periods[0].summary


def test_accuweather_location_contract(client: httpx.Client) -> None:
    with recorder.use_cassette("accuweather_location_search.yaml"):
        latitude, longitude = _coords(default_lat=44.639, default_lon=-63.587)
        location = fetch_accuweather_location(
            latitude=latitude,
            longitude=longitude,
            api_key=_accuweather_key(),
            client=client,
        )

    assert location.key
    assert location.location.latitude == pytest.approx(latitude, abs=0.05)
    assert location.location.longitude == pytest.approx(longitude, abs=0.05)


def test_accuweather_observation_contract(client: httpx.Client) -> None:
    with recorder.use_cassette("accuweather_location_search.yaml"):
        latitude, longitude = _coords(default_lat=44.639, default_lon=-63.587)
        location = fetch_accuweather_location(
            latitude=latitude,
            longitude=longitude,
            api_key=_accuweather_key(),
            client=client,
        )

    with recorder.use_cassette("accuweather_observation.yaml"):
        observation = fetch_accuweather_observation(
            location_key=location.key,
            latitude=latitude,
            longitude=longitude,
            api_key=_accuweather_key(),
            client=client,
        )

    assert observation.provider == "accuweather"
    assert observation.location.latitude == pytest.approx(latitude, abs=0.05)
    assert observation.location.longitude == pytest.approx(longitude, abs=0.05)
    assert observation.temperature_c is not None
    assert observation.temperature_apparent_c is not None
    assert observation.wind_gust_kph is not None
    assert observation.uv_index is not None


def test_accuweather_hourly_forecast_contract(client: httpx.Client) -> None:
    with recorder.use_cassette("accuweather_location_search.yaml"):
        latitude, longitude = _coords(default_lat=44.639, default_lon=-63.587)
        location = fetch_accuweather_location(
            latitude=latitude,
            longitude=longitude,
            api_key=_accuweather_key(),
            client=client,
        )

    with recorder.use_cassette("accuweather_forecast_hourly.yaml"):
        periods = fetch_accuweather_hourly_forecast(
            location_key=location.key,
            latitude=latitude,
            longitude=longitude,
            api_key=_accuweather_key(),
            client=client,
        )

    assert periods
    assert periods[0].temperature_c is not None
    assert periods[0].temperature_apparent_c is not None
    assert periods[0].wind_gust_kph is not None
    assert periods[0].uv_index is not None
    _assert_period_sequence(periods, expected_step=timedelta(hours=1))


def test_accuweather_daily_forecast_contract(client: httpx.Client) -> None:
    with recorder.use_cassette("accuweather_location_search.yaml"):
        latitude, longitude = _coords(default_lat=44.639, default_lon=-63.587)
        location = fetch_accuweather_location(
            latitude=latitude,
            longitude=longitude,
            api_key=_accuweather_key(),
            client=client,
        )

    with recorder.use_cassette("accuweather_forecast_daily.yaml"):
        periods = fetch_accuweather_daily_forecast(
            location_key=location.key,
            latitude=latitude,
            longitude=longitude,
            api_key=_accuweather_key(),
            client=client,
        )

    assert periods
    assert periods[0].temperature_high_c is not None
    assert periods[0].temperature_apparent_c is not None
    assert periods[0].wind_gust_kph is not None
    assert periods[0].uv_index is not None


def test_openweather_observation_contract(client: httpx.Client) -> None:
    with recorder.use_cassette("openweather_observation.yaml"):
        latitude, longitude = _coords(default_lat=51.51, default_lon=-0.13)
        observation = fetch_openweather_observation(
            latitude=latitude,
            longitude=longitude,
            api_key=_openweather_key(),
            client=client,
        )

    assert observation.provider == "openweather"
    assert observation.location.latitude == pytest.approx(latitude)
    assert observation.location.longitude == pytest.approx(longitude)
    assert observation.condition
    assert observation.temperature_c is not None
    assert observation.temperature_apparent_c is not None


def test_openweather_forecast_contract(client: httpx.Client) -> None:
    with recorder.use_cassette("openweather_forecast.yaml"):
        latitude, longitude = _coords(default_lat=51.51, default_lon=-0.13)
        periods = fetch_openweather_forecast(
            latitude=latitude,
            longitude=longitude,
            api_key=_openweather_key(),
            client=client,
        )

    assert periods
    assert periods[0].summary
    assert periods[0].temperature_c is not None
    assert periods[0].relative_humidity is not None
    assert periods[0].pressure_sea_level_kpa is not None
    _assert_period_sequence(periods, expected_step=timedelta(hours=3))


def test_openweather_onecall_hourly_contract(client: httpx.Client) -> None:
    with recorder.use_cassette("openweather_onecall_hourly.yaml"):
        latitude, longitude = _coords(default_lat=51.51, default_lon=-0.13)
        periods = fetch_openweather_onecall_hourly(
            latitude=latitude,
            longitude=longitude,
            api_key=_openweather_key(),
            client=client,
        )

    assert periods
    assert periods[0].temperature_c is not None
    assert periods[0].temperature_apparent_c is not None
    assert periods[0].wind_gust_kph is not None
    assert periods[0].uv_index is not None
    assert periods[0].dewpoint_c is not None
    assert periods[0].relative_humidity is not None
    assert periods[0].pressure_sea_level_kpa is not None
    assert periods[0].cloud_cover_pct is not None
    assert periods[0].condition_code is not None
    _assert_period_sequence(periods, expected_step=timedelta(hours=1))
    _assert_period_sequence(periods, expected_step=timedelta(hours=1))


def test_openweather_onecall_daily_contract(client: httpx.Client) -> None:
    with recorder.use_cassette("openweather_onecall_daily.yaml"):
        latitude, longitude = _coords(default_lat=51.51, default_lon=-0.13)
        periods = fetch_openweather_onecall_daily(
            latitude=latitude,
            longitude=longitude,
            api_key=_openweather_key(),
            client=client,
        )

    assert periods
    assert periods[0].temperature_high_c is not None
    assert periods[0].temperature_apparent_c is not None
    assert periods[0].wind_gust_kph is not None
    assert periods[0].uv_index is not None
    assert periods[0].dewpoint_c is not None
    assert periods[0].relative_humidity is not None
    assert periods[0].pressure_sea_level_kpa is not None
    assert periods[0].cloud_cover_pct is not None
    assert periods[0].condition_code is not None
    _assert_period_sequence(periods, expected_step=timedelta(days=1))


def test_tomorrow_io_observation_contract(client: httpx.Client) -> None:
    with recorder.use_cassette("tomorrow_io_observation.yaml"):
        latitude, longitude = _coords(default_lat=40.7, default_lon=-74.0)
        observation = fetch_tomorrow_io_observation(
            latitude=latitude,
            longitude=longitude,
            api_key=_tomorrow_io_key(),
            client=client,
        )

    assert observation.provider == "tomorrow_io"
    assert observation.location.latitude == pytest.approx(latitude)
    assert observation.location.longitude == pytest.approx(longitude)
    assert observation.condition
    assert observation.precipitation_last_hour_mm is not None
    assert observation.temperature_apparent_c is not None
    assert observation.wind_gust_kph is not None
    assert observation.uv_index is not None
    assert observation.pressure_surface_kpa is not None
    assert observation.cloud_cover_pct is not None
    assert observation.condition_code is not None


def test_tomorrow_io_forecast_contract(client: httpx.Client) -> None:
    with recorder.use_cassette("tomorrow_io_forecast.yaml"):
        latitude, longitude = _coords(default_lat=40.7, default_lon=-74.0)
        periods = fetch_tomorrow_io_forecast(
            latitude=latitude,
            longitude=longitude,
            api_key=_tomorrow_io_key(),
            client=client,
        )

    assert periods
    assert periods[0].location.latitude == pytest.approx(latitude)
    assert periods[0].location.longitude == pytest.approx(longitude)
    assert periods[0].temperature_c is not None
    assert periods[0].temperature_apparent_c is not None
    assert periods[0].wind_gust_kph is not None
    assert periods[0].uv_index is not None
    assert periods[0].relative_humidity is not None
    assert periods[0].pressure_sea_level_kpa is not None
    assert periods[0].cloud_cover_pct is not None
    assert periods[0].condition_code is not None


def test_tomorrow_io_daily_forecast_contract(client: httpx.Client) -> None:
    with recorder.use_cassette("tomorrow_io_forecast_daily.yaml"):
        latitude, longitude = _coords(default_lat=40.7, default_lon=-74.0)
        periods = fetch_tomorrow_io_daily_forecast(
            latitude=latitude,
            longitude=longitude,
            api_key=_tomorrow_io_key(),
            client=client,
        )

    assert periods
    assert periods[0].temperature_high_c is not None
    assert periods[0].temperature_apparent_c is not None
    assert periods[0].wind_gust_kph is not None
    assert periods[0].uv_index is not None
    assert periods[0].relative_humidity is not None
    assert periods[0].precipitation_amount_rain_mm is not None
    assert periods[0].cloud_cover_pct is not None
    _assert_period_sequence(periods, expected_step=timedelta(days=1))


def test_msc_geomet_observation_contract(client: httpx.Client) -> None:
    with recorder.use_cassette("msc_geomet_observation.yaml"):
        latitude, longitude = _coords(default_lat=45.421, default_lon=-75.697)
        observation = fetch_msc_geomet_observation(
            latitude=latitude,
            longitude=longitude,
            client=client,
        )

    assert observation.provider == "msc_geomet"
    assert observation.location.latitude is not None
    assert observation.location.longitude is not None
    assert observation.condition
    assert observation.temperature_wind_chill_c is not None


def test_msc_geomet_forecast_contract(client: httpx.Client) -> None:
    with recorder.use_cassette("msc_geomet_forecast.yaml"):
        latitude, longitude = _coords(default_lat=45.421, default_lon=-75.697)
        periods = fetch_msc_geomet_forecast(
            latitude=latitude,
            longitude=longitude,
            client=client,
        )

    assert periods
    assert periods[0].location.latitude is not None
    assert periods[0].location.longitude is not None
    assert periods[0].summary
    assert periods[0].relative_humidity is not None
    _assert_period_sequence(periods, min_step=timedelta(hours=1))


def test_msc_rdps_prognos_forecast_contract(client: httpx.Client) -> None:
    with recorder.use_cassette("msc_rdps_prognos_forecast.yaml"):
        latitude, longitude = _coords(default_lat=45.421, default_lon=-75.697)
        run_time = datetime(2025, 12, 28, 0, tzinfo=timezone.utc)
        periods = fetch_msc_rdps_prognos_forecast(
            latitude=latitude,
            longitude=longitude,
            client=client,
            max_lead_hours=0,
            run_time=run_time,
        )

    assert periods
    assert periods[0].temperature_c is not None
    assert periods[0].dewpoint_c is not None
    assert periods[0].wind_speed_kph is not None
    assert periods[0].wind_direction_deg is not None
    _assert_period_sequence(periods, expected_step=timedelta(hours=1))


def test_weatherkit_weather_contract(client: httpx.Client, tmp_path: Path) -> None:
    with recorder.use_cassette("weatherkit_weather.yaml"):
        latitude, longitude = _coords(default_lat=44.639, default_lon=-63.587)
        bundle = fetch_weatherkit_bundle(
            latitude=latitude,
            longitude=longitude,
            timezone_name=os.getenv("WX_TZ", "America/Halifax"),
            country_code="CA",
            client=client,
            team_id=_weatherkit_team_id(),
            service_id=_weatherkit_service_id(),
            key_id=_weatherkit_key_id(),
            key_path=_weatherkit_key_path(tmp_path),
        )

    assert bundle.observation is not None
    assert bundle.observation.temperature_c is not None
    assert bundle.hourly
    assert bundle.daily
    assert bundle.next_hour
    _assert_period_sequence(bundle.next_hour, expected_step=timedelta(minutes=1))
    assert bundle.alerts == []
