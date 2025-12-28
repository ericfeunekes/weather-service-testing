from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest
import vcr

from wxbench.providers import (
    fetch_msc_geomet_forecast,
    fetch_msc_geomet_observation,
    fetch_ambient_weather_observation,
    fetch_openweather_forecast,
    fetch_openweather_observation,
    fetch_tomorrow_io_forecast,
    fetch_tomorrow_io_observation,
)
from wxbench.providers.errors import ProviderAuthError


CASSETTE_DIR = Path(__file__).parent / "cassettes"

recorder = vcr.VCR(
    cassette_library_dir=str(CASSETTE_DIR),
    record_mode=os.getenv("WX_VCR_RECORD_MODE", "none"),
    filter_query_parameters=[
        ("appid", "REDACTED"),
        ("apikey", "REDACTED"),
        ("apiKey", "REDACTED"),
        ("applicationKey", "REDACTED"),
    ],
    filter_headers=["authorization"],
    match_on=["method", "scheme", "host", "port", "path", "query"],
)


RECORDING = recorder.record_mode != "none"

DEFAULT_AMBIENT_API_KEY = "super-secret"
DEFAULT_AMBIENT_APPLICATION_KEY = "another-secret"
DEFAULT_OPENWEATHER_API_KEY = "super-secret"
DEFAULT_TOMORROW_IO_API_KEY = "another-secret"


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


def _openweather_key() -> str:
    return _require_env("WX_OPENWEATHER_API_KEY", provider="OpenWeather") or DEFAULT_OPENWEATHER_API_KEY


def _tomorrow_io_key() -> str:
    return _require_env("WX_TOMORROW_IO_API_KEY", provider="Tomorrow.io") or DEFAULT_TOMORROW_IO_API_KEY


def _coords(*, default_lat: float, default_lon: float) -> tuple[float, float]:
    lat_raw = os.getenv("WX_LAT")
    lon_raw = os.getenv("WX_LON")
    if lat_raw and lon_raw:
        try:
            return float(lat_raw), float(lon_raw)
        except ValueError:
            pytest.skip("Invalid coordinates provided via WX_LAT/WX_LON")
    return default_lat, default_lon


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
            client=client,
        )

    assert observation.provider == "ambient_weather"
    assert observation.station
    assert observation.location.latitude is not None
    assert observation.location.longitude is not None
    assert observation.temperature_c is not None


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
