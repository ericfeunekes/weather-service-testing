"""Provider adapters sit at the boundary.

Each provider module exposes a small interface for fetching data, keeping HTTP
configuration, retries, and auth details isolated from the pure domain layer.
Use dependency injection for clients and clocks to keep integration points
testable.
"""

from wxbench.providers.accuweather import (
    fetch_accuweather_daily_forecast,
    fetch_accuweather_hourly_forecast,
    fetch_accuweather_location,
    fetch_accuweather_minute_forecast,
    fetch_accuweather_observation,
)
from wxbench.providers.ambient_weather import fetch_ambient_weather_observation
from wxbench.providers.msc_geomet import fetch_msc_geomet_forecast, fetch_msc_geomet_observation
from wxbench.providers.msc_rdps_prognos import fetch_msc_rdps_prognos_forecast, rdps_prognos_endpoint
from wxbench.providers.openweather import (
    fetch_openweather_forecast,
    fetch_openweather_observation,
    fetch_openweather_onecall_daily,
    fetch_openweather_onecall_hourly,
)
from wxbench.providers.tomorrow_io import (
    fetch_tomorrow_io_daily_forecast,
    fetch_tomorrow_io_forecast,
    fetch_tomorrow_io_observation,
)

__all__ = [
    "fetch_accuweather_daily_forecast",
    "fetch_accuweather_hourly_forecast",
    "fetch_accuweather_location",
    "fetch_accuweather_minute_forecast",
    "fetch_accuweather_observation",
    "fetch_ambient_weather_observation",
    "fetch_msc_geomet_forecast",
    "fetch_msc_geomet_observation",
    "fetch_msc_rdps_prognos_forecast",
    "rdps_prognos_endpoint",
    "fetch_openweather_forecast",
    "fetch_openweather_observation",
    "fetch_openweather_onecall_daily",
    "fetch_openweather_onecall_hourly",
    "fetch_tomorrow_io_daily_forecast",
    "fetch_tomorrow_io_forecast",
    "fetch_tomorrow_io_observation",
]
