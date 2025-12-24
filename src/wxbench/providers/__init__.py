"""Provider adapters sit at the boundary.

Each provider module exposes a small interface for fetching data, keeping HTTP
configuration, retries, and auth details isolated from the pure domain layer.
Use dependency injection for clients and clocks to keep integration points
testable.
"""

from wxbench.providers.msc_geomet import fetch_msc_geomet_forecast, fetch_msc_geomet_observation
from wxbench.providers.openweather import fetch_openweather_forecast, fetch_openweather_observation
from wxbench.providers.tomorrow_io import fetch_tomorrow_io_forecast, fetch_tomorrow_io_observation

__all__ = [
    "fetch_msc_geomet_forecast",
    "fetch_msc_geomet_observation",
    "fetch_openweather_forecast",
    "fetch_openweather_observation",
    "fetch_tomorrow_io_forecast",
    "fetch_tomorrow_io_observation",
]
