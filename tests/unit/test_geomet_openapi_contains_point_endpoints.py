from __future__ import annotations

from pathlib import Path
import json


SPEC_PATH = Path(__file__).resolve().parents[2] / "specs" / "msc-geomet.json"
EXPECTED_ENDPOINTS = {
    "/collections/observations/point",
    "/collections/forecasts/point",
}


def test_geomet_openapi_contains_point_endpoints() -> None:
    spec = json.loads(SPEC_PATH.read_text())
    paths = spec.get("paths", {})
    assert isinstance(paths, dict), "OpenAPI document must contain a paths object"

    missing = EXPECTED_ENDPOINTS.difference(paths)
    assert not missing, f"GeoMet OpenAPI snapshot missing endpoints: {sorted(missing)}"
