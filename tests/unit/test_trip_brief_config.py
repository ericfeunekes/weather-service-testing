from pathlib import Path

import yaml

from wxbench.trip_brief.config import load_trip_brief_config


def test_load_trip_brief_config_overrides(tmp_path: Path) -> None:
    config = {
        "defaults": {
            "sampling": {"distance_km": 50, "time_cap_minutes": 40},
            "output": {"format": "markdown", "pdf": False},
            "route": {"travel_mode": "DRIVE", "routing_preference": "TRAFFIC_AWARE", "units": "METRIC"},
            "msc": {"mode": "endpoints"},
            "timezone": "America/Halifax",
        },
        "routes": {
            "test_route": {
                "name": "Test",
                "origin": "A",
                "destination": "B",
                "sampling": {"distance_km": 25},
            }
        },
    }
    path = tmp_path / "routes.yaml"
    path.write_text(yaml.safe_dump(config))

    loaded = load_trip_brief_config(
        config_path=path,
        route_id="test_route",
        origin=None,
        destination=None,
        sampling_distance_km=None,
        sampling_time_cap_minutes=30,
        output_format=None,
        output_path=None,
        pdf=None,
        pdf_path=None,
        timezone=None,
    )

    assert loaded.route.origin == "A"
    assert loaded.sampling.distance_km == 25
    assert loaded.sampling.time_cap_minutes == 30
    assert loaded.msc.mode == "endpoints"
