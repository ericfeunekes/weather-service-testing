from __future__ import annotations

from datetime import datetime, timezone

import httpx

from wxbench.providers.accuweather import fetch_accuweather_minute_forecast


def test_minutecast_request_uses_exact_coordinate_and_auth_header() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/forecasts/v1/minute"
        assert request.url.params["q"] == "45.421,-75.697"
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            request=request,
            json={
                "Summary": {"Phrase": "No precipitation"},
                "Summaries": [
                    {
                        "StartMinute": 0,
                        "EndMinute": 59,
                        "MinuteText": "No precipitation",
                    }
                ],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        periods = fetch_accuweather_minute_forecast(
            latitude=45.421,
            longitude=-75.697,
            api_key="test-key",
            client=client,
            retries=0,
            clock=lambda: datetime(2026, 8, 15, tzinfo=timezone.utc),
        )

    assert periods
