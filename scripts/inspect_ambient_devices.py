"""Inspect Ambient Weather devices and summarize available fields."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

import httpx

BASE_URL = "https://api.ambientweather.net/v1/devices"


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value.strip()


def _format_ts(value: Any) -> str:
    if value is None:
        return "unknown"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    if numeric > 10**12:
        numeric /= 1000.0
    return datetime.fromtimestamp(numeric, tz=timezone.utc).isoformat()


def _device_summary(device: Mapping[str, Any]) -> dict[str, Any]:
    info = device.get("info") or {}
    last_data = device.get("lastData") or {}
    coords = info.get("coords") or {}
    if isinstance(coords, Mapping) and "coords" in coords:
        coords = coords.get("coords") or {}

    return {
        "macAddress": device.get("macAddress"),
        "name": info.get("name"),
        "location": info.get("location"),
        "latitude": coords.get("lat") or coords.get("latitude"),
        "longitude": coords.get("lon") or coords.get("longitude"),
        "lastDataTimestamp": _format_ts(last_data.get("dateutc")),
        "lastDataKeys": sorted([str(key) for key in last_data.keys()]),
    }


def main() -> int:
    api_key = _require_env("WX_AMBIENT_API_KEY")
    application_key = _require_env("WX_AMBIENT_APPLICATION_KEY")

    params = {"apiKey": api_key, "applicationKey": application_key}

    with httpx.Client(timeout=10.0) as client:
        response = client.get(BASE_URL, params=params, headers={"accept": "application/json"})
        response.raise_for_status()
        payload = response.json()

    if not isinstance(payload, Sequence):
        raise RuntimeError("Unexpected payload: expected a list of devices")

    summaries = [_device_summary(device) for device in payload if isinstance(device, Mapping)]
    print(json.dumps({"deviceCount": len(summaries), "devices": summaries}, indent=2, sort_keys=True))

    output_path = os.getenv("WX_AMBIENT_DUMP_PATH")
    if output_path:
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        print(f"Wrote raw payload to {output_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        raise
