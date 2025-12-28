from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import httpx
from dotenv import load_dotenv


@dataclass(frozen=True)
class RequestSpec:
    name: str
    url: str
    params: dict[str, str]
    headers: dict[str, str]


def _mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _redact_params(params: dict[str, str]) -> dict[str, str]:
    redacted: dict[str, str] = {}
    for key, value in params.items():
        if key.lower() in {"apikey", "api_key", "apiKey"}:
            redacted[key] = _mask_secret(value)
        else:
            redacted[key] = value
    return redacted


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    redacted: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in {"apikey", "authorization"}:
            redacted[key] = _mask_secret(value)
        else:
            redacted[key] = value
    return redacted


def _build_requests(api_key: str) -> Iterable[RequestSpec]:
    base = "https://api.tomorrow.io/v4"
    common_params = {"location": "40.7,-74.0", "units": "metric"}
    accept_header = {"accept": "application/json"}

    yield RequestSpec(
        name="realtime-query-apikey",
        url=f"{base}/weather/realtime",
        params={**common_params, "apikey": api_key},
        headers=accept_header,
    )

    yield RequestSpec(
        name="realtime-header-apikey",
        url=f"{base}/weather/realtime",
        params=common_params,
        headers={**accept_header, "apikey": api_key},
    )

    yield RequestSpec(
        name="timelines-query-apikey",
        url=f"{base}/timelines",
        params={
            "location": common_params["location"],
            "fields": "temperature",
            "timesteps": "1h",
            "units": "metric",
            "apikey": api_key,
        },
        headers=accept_header,
    )

    yield RequestSpec(
        name="timelines-header-apikey",
        url=f"{base}/timelines",
        params={
            "location": common_params["location"],
            "fields": "temperature",
            "timesteps": "1h",
            "units": "metric",
        },
        headers={**accept_header, "apikey": api_key},
    )


def main() -> int:
    load_dotenv(dotenv_path=Path(".env"))
    api_key = os.getenv("WX_TOMORROW_IO_API_KEY", "").strip()
    if not api_key:
        print("Missing WX_TOMORROW_IO_API_KEY in .env or environment.")
        return 1

    timeout = httpx.Timeout(10.0, connect=5.0)
    with httpx.Client(timeout=timeout) as client:
        for spec in _build_requests(api_key):
            print(f"\n== {spec.name} ==")
            print("request", spec.url)
            print("params", _redact_params(spec.params))
            print("headers", _redact_headers(spec.headers))

            try:
                response = client.get(spec.url, params=spec.params, headers=spec.headers)
            except httpx.HTTPError as exc:
                print("error", type(exc).__name__, str(exc))
                continue

            print("status", response.status_code)
            content_type = response.headers.get("content-type", "")
            print("content-type", content_type)
            text = response.text
            if text:
                print("body", text[:500])
            else:
                print("body <empty>")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
