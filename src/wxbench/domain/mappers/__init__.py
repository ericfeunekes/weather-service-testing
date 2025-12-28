"""Provider payload mappers."""

from wxbench.domain.mappers.accuweather import (
    map_accuweather_daily_forecast,
    map_accuweather_hourly_forecast,
    map_accuweather_location,
    map_accuweather_minute_forecast,
    map_accuweather_observation,
)
from wxbench.domain.mappers.ambient_weather import map_ambient_weather_observation
from wxbench.domain.mappers.msc_geomet import map_msc_geomet_forecast, map_msc_geomet_observation
from wxbench.domain.mappers.openweather import (
    map_openweather_forecast,
    map_openweather_observation,
    map_openweather_onecall_daily,
    map_openweather_onecall_hourly,
)
from wxbench.domain.mappers.tomorrow_io import (
    map_tomorrow_io_daily_forecast,
    map_tomorrow_io_forecast,
    map_tomorrow_io_observation,
)

__all__ = [
    "map_accuweather_daily_forecast",
    "map_accuweather_hourly_forecast",
    "map_accuweather_location",
    "map_accuweather_minute_forecast",
    "map_accuweather_observation",
    "map_ambient_weather_observation",
    "map_msc_geomet_observation",
    "map_msc_geomet_forecast",
    "map_openweather_observation",
    "map_openweather_forecast",
    "map_openweather_onecall_daily",
    "map_openweather_onecall_hourly",
    "map_tomorrow_io_observation",
    "map_tomorrow_io_forecast",
    "map_tomorrow_io_daily_forecast",
]
