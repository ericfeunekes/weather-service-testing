from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
import respx

from wxbench.providers.errors import ProviderRequestError
from wxbench.providers.msc_rdps_prognos import (
    _VARIABLES,
    _build_filename,
    _resolve_run_time,
)


def test_builds_current_rdps_prognos_filenames() -> None:
    run_time = datetime(2026, 8, 14, 6, tzinfo=timezone.utc)

    assert _build_filename(run_time, 0, _VARIABLES[0]) == (
        "20260814T06Z_MSC_RDPS-PROGNOS-MLR_AirTemp_AGL-1.5m_PT000H.json"
    )
    assert _build_filename(run_time, 0, _VARIABLES[2]) == (
        "20260814T06Z_MSC_RDPS-PROGNOS-LightGBM_WindSpeed_AGL-10m_PT000H.json"
    )


def test_run_resolution_falls_back_from_unpublished_cycle() -> None:
    now = datetime(2026, 8, 14, 13, tzinfo=timezone.utc)
    current = "/12/000/20260814T12Z_MSC_RDPS-PROGNOS-MLR_AirTemp_AGL-1.5m_PT000H.json"
    previous = "/06/000/20260814T06Z_MSC_RDPS-PROGNOS-MLR_AirTemp_AGL-1.5m_PT000H.json"

    with respx.mock(base_url="https://example.com") as mock:
        mock.get(current).respond(404)
        mock.get(previous).respond(200, json={"features": []})
        transport = httpx.MockTransport(mock.handler)
        with httpx.Client(transport=transport) as client:
            resolved, payload = _resolve_run_time(
                now=now,
                client=client,
                base_url="https://example.com",
                timeout=1.0,
                retries=0,
                capture=None,
            )

    assert resolved == datetime(2026, 8, 14, 6, tzinfo=timezone.utc)
    assert payload == {"features": []}


def test_run_resolution_uses_dated_archive_across_utc_midnight() -> None:
    now = datetime(2026, 8, 15, 0, 13, tzinfo=timezone.utc)
    current = (
        "https://dd.weather.gc.ca/today/model_rdps/stat-post-processing/00/000/"
        "20260815T00Z_MSC_RDPS-PROGNOS-MLR_AirTemp_AGL-1.5m_PT000H.json"
    )
    previous = (
        "https://dd.weather.gc.ca/20260814/WXO-DD/model_rdps/stat-post-processing/18/000/"
        "20260814T18Z_MSC_RDPS-PROGNOS-MLR_AirTemp_AGL-1.5m_PT000H.json"
    )

    with respx.mock() as mock:
        mock.get(current).respond(404)
        mock.get(previous).respond(200, json={"features": []})
        transport = httpx.MockTransport(mock.handler)
        with httpx.Client(transport=transport) as client:
            resolved, payload = _resolve_run_time(
                now=now,
                client=client,
                base_url="https://dd.weather.gc.ca/today/model_rdps/stat-post-processing",
                timeout=1.0,
                retries=0,
                capture=None,
            )

    assert resolved == datetime(2026, 8, 14, 18, tzinfo=timezone.utc)
    assert payload == {"features": []}


def test_run_resolution_preserves_failure_when_all_cycles_are_missing() -> None:
    now = datetime(2026, 8, 14, 13, tzinfo=timezone.utc)

    with respx.mock(base_url="https://example.com") as mock:
        mock.get(url__regex=r"https://example\.com/.+").respond(404)
        transport = httpx.MockTransport(mock.handler)
        with httpx.Client(transport=transport) as client:
            with pytest.raises(ProviderRequestError, match="No available RDPS PROGNOS run found"):
                _resolve_run_time(
                    now=now,
                    client=client,
                    base_url="https://example.com",
                    timeout=1.0,
                    retries=0,
                    capture=None,
                )
