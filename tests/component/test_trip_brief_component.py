from datetime import datetime, timedelta, timezone

from wxbench.domain.models import ForecastPeriod, Location, Observation
from wxbench.providers.google_routes import GoogleRoute
from wxbench.trip_brief.runner import generate_trip_brief


def test_trip_brief_component_with_fakes() -> None:
    encoded = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
    route = GoogleRoute(
        geometry=[],
        distance_km=500.0,
        duration_seconds=5 * 3600.0,
        encoded_polyline=encoded,
    )

    def route_fetcher():
        return route

    def weather_fetcher(lat: float, lon: float, tz_name: str):
        issued = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
        start = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)
        return [
            ForecastPeriod(
                provider="fake",
                location=Location(latitude=lat, longitude=lon),
                issued_at=issued,
                start_time=start,
                end_time=start + timedelta(hours=1),
                temperature_c=1.0,
                precipitation_probability=20.0,
                precipitation_mm=0.2,
                wind_speed_kph=10.0,
                wind_gust_kph=20.0,
                visibility_km=5.0,
                precipitation_rate_snow_mm_hr=0.0,
            )
        ]

    def msc_fetcher(lat: float, lon: float) -> Observation:
        return Observation(
            provider="msc",
            station=None,
            location=Location(latitude=lat, longitude=lon),
            observed_at=datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc),
            temperature_c=0.0,
            wind_speed_kph=5.0,
            visibility_km=10.0,
        )

    result = generate_trip_brief(
        name="Test Route",
        depart_time=datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc),
        timezone="UTC",
        sampling_distance_km=200.0,
        sampling_time_cap_minutes=120.0,
        route_fetcher=route_fetcher,
        weather_fetcher=weather_fetcher,
        msc_mode="endpoints",
        msc_fetcher=msc_fetcher,
    )

    assert "Trip Brief" in result.markdown
    assert result.rows
    assert len(result.msc_observations) == 2
