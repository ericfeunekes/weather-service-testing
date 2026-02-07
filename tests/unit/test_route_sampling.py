from datetime import datetime, timezone

from wxbench.trip_brief.sampling import sample_route_points


def test_sample_route_points_includes_endpoints() -> None:
    geometry = [(0.0, 0.0), (0.0, 1.0)]
    samples = sample_route_points(
        geometry,
        total_distance_km=111.0,
        duration_seconds=3600.0,
        distance_km=50.0,
        time_cap_minutes=40.0,
        depart_time=datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc),
    )
    assert samples[0].distance_km == 0.0
    assert samples[-1].distance_km == 111.0
    assert len(samples) >= 3
    assert samples[1].distance_km > 0.0
