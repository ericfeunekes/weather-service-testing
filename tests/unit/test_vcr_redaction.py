from __future__ import annotations

import json
from types import SimpleNamespace

from tests.vcr_redaction import redact_request, redact_response


def test_redacts_ambient_device_identifier_from_request_path() -> None:
    request = SimpleNamespace(
        uri="https://api.ambientweather.net/v1/devices/AA:BB:CC?apiKey=REDACTED"
    )

    assert redact_request(request) is request
    assert request.uri == (
        "https://api.ambientweather.net/v1/devices/REDACTED?apiKey=REDACTED"
    )


def test_redacts_legacy_minutecast_coordinate() -> None:
    request = SimpleNamespace(
        uri="https://dataservice.accuweather.com/forecasts/v1/minute?q=45.421%2C-75.697"
    )

    redact_request(request)

    assert request.uri == (
        "https://dataservice.accuweather.com/forecasts/v1/minute?q=REDACTED"
    )


def test_redacts_ambient_station_identity_and_location() -> None:
    response = {
        "body": {
            "string": json.dumps(
                [
                    {
                        "macAddress": "AA:BB:CC:DD:EE:FF",
                        "lastData": {"tempf": 68.0},
                        "info": {
                            "name": "Home",
                            "coords": {"lat": 44.0, "lon": -63.0},
                            "address": "private address",
                        },
                    }
                ]
            ).encode()
        },
        "headers": {
            "Content-Length": ["999"],
            "Content-Type": ["application/json"],
            "Set-Cookie": ["private-token"],
            "X-Aw-Id": ["contains-client-ip"],
        },
    }

    redacted = redact_response(response)
    payload = json.loads(redacted["body"]["string"])

    assert payload == [
        {
            "macAddress": "REDACTED",
            "lastData": {"tempf": 68.0},
            "info": {"name": "REDACTED", "coords": [0.0, 0.0]},
        }
    ]
    assert redacted["headers"]["Content-Length"] == [
        str(len(redacted["body"]["string"]))
    ]
    assert set(redacted["headers"]) == {"Content-Length", "Content-Type"}


def test_leaves_unrelated_json_responses_unchanged() -> None:
    response = {"body": {"string": b'{"temperature":21}'}, "headers": {}}

    assert redact_response(response) is response
    assert response["body"]["string"] == b'{"temperature":21}'
