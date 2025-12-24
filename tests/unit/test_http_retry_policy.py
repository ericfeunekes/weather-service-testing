from __future__ import annotations

import httpx
import pytest
import respx

from wxbench.providers._http import send_with_retries
from wxbench.providers.errors import ProviderAuthError, ProviderPayloadError, ProviderTransientError
from wxbench.providers.openweather import fetch_openweather_observation


def test_retries_429_with_retry_after_and_succeeds() -> None:
    sleeps: list[float] = []

    with respx.mock(base_url="https://example.com") as mock:
        mock.get("/data").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "2"}),
                httpx.Response(200, json={"ok": True}),
            ]
        )

        transport = httpx.MockTransport(mock.handler)

        with httpx.Client(base_url="https://example.com", transport=transport) as client:
            request = client.build_request("GET", "/data")
            response = send_with_retries(
                client,
                request,
                provider="example",
                operation="test",
                retries=1,
                sleep=sleeps.append,
            )

    assert response.status_code == 200
    assert sleeps == [2.0]


def test_retries_500_and_succeeds() -> None:
    sleeps: list[float] = []

    with respx.mock(base_url="https://example.com") as mock:
        mock.get("/data").mock(
            side_effect=[httpx.Response(500), httpx.Response(200, json={"ok": True})]
        )

        transport = httpx.MockTransport(mock.handler)

        with httpx.Client(base_url="https://example.com", transport=transport) as client:
            request = client.build_request("GET", "/data")
            response = send_with_retries(
                client,
                request,
                provider="example",
                operation="test",
                retries=1,
                sleep=sleeps.append,
            )

    assert response.status_code == 200
    assert sleeps == [0.25]


def test_timeouts_raise_transient_error() -> None:
    sleeps: list[float] = []

    with respx.mock(base_url="https://example.com") as mock:
        mock.get("/data").mock(side_effect=[httpx.ReadTimeout("timeout"), httpx.ReadTimeout("timeout")])

        transport = httpx.MockTransport(mock.handler)

        with httpx.Client(base_url="https://example.com", transport=transport) as client:
            request = client.build_request("GET", "/data")

            with pytest.raises(ProviderTransientError):
                send_with_retries(
                    client,
                    request,
                    provider="example",
                    operation="test",
                    retries=1,
                    sleep=sleeps.append,
                )

    assert sleeps == [0.25]


def test_auth_error_no_retries() -> None:
    sleeps: list[float] = []

    with respx.mock(base_url="https://example.com") as mock:
        mock.get("/data").mock(return_value=httpx.Response(401))

        transport = httpx.MockTransport(mock.handler)

        with httpx.Client(base_url="https://example.com", transport=transport) as client:
            request = client.build_request("GET", "/data")

            with pytest.raises(ProviderAuthError):
                send_with_retries(
                    client,
                    request,
                    provider="example",
                    operation="test",
                    retries=3,
                    sleep=sleeps.append,
                )

    assert sleeps == []


def test_malformed_json_raises_payload_error() -> None:
    with respx.mock(base_url="https://api.openweathermap.org") as mock:
        mock.get("/data/2.5/weather").mock(return_value=httpx.Response(200, text="not-json"))

        transport = httpx.MockTransport(mock.handler)

        with httpx.Client(transport=transport) as client:
            with pytest.raises(ProviderPayloadError):
                fetch_openweather_observation(
                    latitude=1.0,
                    longitude=2.0,
                    api_key="abc",
                    client=client,
                )

