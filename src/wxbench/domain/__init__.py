"""Pure domain logic lives here.

Keep these modules side-effect free: functions should accept data as input and
return data as output. Parsing, validation, normalization, and scoring belong
in this layer so they can be tested with fast unit tests.
"""

from .models import DataPoint, ForecastPeriod, Location, Observation

__all__ = ["DataPoint", "ForecastPeriod", "Location", "Observation"]
