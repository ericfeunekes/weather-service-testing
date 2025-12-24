"""Provider payload mappers."""

from wxbench.domain.mappers.ambient_weather import map_ambient_weather_observation
from wxbench.domain.mappers.msc_geomet import map_msc_geomet_forecast, map_msc_geomet_observation
from wxbench.domain.mappers.openweather import map_openweather_forecast, map_openweather_observation
from wxbench.domain.mappers.tomorrow_io import map_tomorrow_io_forecast, map_tomorrow_io_observation

__all__ = [
    "map_ambient_weather_observation",
    "map_msc_geomet_observation",
    "map_msc_geomet_forecast",
    "map_openweather_observation",
    "map_openweather_forecast",
    "map_tomorrow_io_observation",
    "map_tomorrow_io_forecast",
]
