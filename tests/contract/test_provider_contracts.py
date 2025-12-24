from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest
import vcr

from wxbench.providers import (
    fetch_msc_geomet_forecast,
    fetch_msc_geomet_observation,
    fetch_openweather_forecast,
    fetch_openweather_observation,
    fetch_tomorrow_io_forecast,
    fetch_tomorrow_io_observation,
)


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


@pytest.fixture()
def client() -> httpx.Client:
    with httpx.Client() as session:
        yield session


def test_openweather_observation_contract(client: httpx.Client) -> None:
    with recorder.use_cassette("openweather_observation.yaml"):
        observation = fetch_openweather_observation(
            latitude=51.51,
            longitude=-0.13,
            api_key="super-secret",
            client=client,
        )

    assert observation.provider == "openweather"
    assert observation.location.latitude == pytest.approx(51.51)
    assert observation.location.longitude == pytest.approx(-0.13)
    assert observation.condition == "light rain"
    assert observation.temperature_c == pytest.approx(16.67, rel=0.01)


def test_openweather_forecast_contract(client: httpx.Client) -> None:
    with recorder.use_cassette("openweather_forecast.yaml"):
        periods = fetch_openweather_forecast(
            latitude=51.51,
            longitude=-0.13,
            api_key="super-secret",
            client=client,
        )

    assert len(periods) == 2
    assert periods[0].summary == "few clouds"
    assert periods[1].precipitation_mm == pytest.approx(0.7)


def test_tomorrow_io_observation_contract(client: httpx.Client) -> None:
    with recorder.use_cassette("tomorrow_io_observation.yaml"):
        observation = fetch_tomorrow_io_observation(
            latitude=40.7,
            longitude=-74.0,
            api_key="another-secret",
            client=client,
        )

    assert observation.provider == "tomorrow_io"
    assert observation.condition == "Light Rain"
    assert observation.precipitation_last_hour_mm == pytest.approx(0.1)


def test_tomorrow_io_forecast_contract(client: httpx.Client) -> None:
    with recorder.use_cassette("tomorrow_io_forecast.yaml"):
        periods = fetch_tomorrow_io_forecast(
            latitude=40.7,
            longitude=-74.0,
            api_key="another-secret",
            client=client,
        )

    assert len(periods) == 2
    assert periods[0].temperature_c == pytest.approx(16.0)
    assert periods[1].precipitation_mm == pytest.approx(0.4)


def test_msc_geomet_observation_contract(client: httpx.Client) -> None:
    with recorder.use_cassette("msc_geomet_observation.yaml"):
        observation = fetch_msc_geomet_observation(
            latitude=45.4,
            longitude=-75.7,
            client=client,
        )

    assert observation.provider == "msc_geomet"
    assert observation.station == "CARO"
    assert observation.condition == "Rain"


def test_msc_geomet_forecast_contract(client: httpx.Client) -> None:
    with recorder.use_cassette("msc_geomet_forecast.yaml"):
        periods = fetch_msc_geomet_forecast(
            latitude=45.4,
            longitude=-75.7,
            client=client,
        )

    assert len(periods) == 2
    assert periods[0].summary == "Cloudy"
    assert periods[1].precipitation_probability == pytest.approx(60)
