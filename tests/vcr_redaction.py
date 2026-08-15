from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def redact_request(request: Any) -> Any:
    """Remove private identifiers and coordinates from recorded request URLs."""
    request.uri = re.sub(r"(/v1/devices/)[^/?]+", r"\1REDACTED", request.uri)
    parts = urlsplit(request.uri)
    if parts.path.endswith("/forecasts/v1/minute"):
        query = [(name, "REDACTED" if name == "q" else value) for name, value in parse_qsl(parts.query)]
        request.uri = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    return request


def redact_response(response: dict[str, Any]) -> dict[str, Any]:
    """Remove private station data and non-contract headers from recordings."""
    response["headers"] = {
        name: value
        for name, value in response.get("headers", {}).items()
        if name.lower() in {"content-length", "content-type"}
    }
    body = response.get("body", {}).get("string")
    if not isinstance(body, (bytes, str)):
        return response

    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return response

    devices = payload if isinstance(payload, list) else []
    changed = False
    for device in devices:
        if not isinstance(device, dict) or "macAddress" not in device:
            continue
        device["macAddress"] = "REDACTED"
        if "info" in device:
            device["info"] = {"name": "REDACTED", "coords": [0.0, 0.0]}
        changed = True

    if not changed:
        return response

    redacted = json.dumps(payload, separators=(",", ":")).encode()
    response["body"]["string"] = redacted
    for name in response["headers"]:
        if name.lower() == "content-length":
            response["headers"][name] = [str(len(redacted))]
    return response
