"""Pydantic schemas for provider payload validation."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, RootModel


class _BaseModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class OpenWeatherCoord(_BaseModel):
    lat: float
    lon: float


class OpenWeatherObservationPayload(_BaseModel):
    coord: OpenWeatherCoord
    dt: int


class OpenWeatherForecastCity(_BaseModel):
    coord: OpenWeatherCoord


class OpenWeatherForecastEntry(_BaseModel):
    dt: int


class OpenWeatherForecastPayload(_BaseModel):
    city: OpenWeatherForecastCity
    list: List[OpenWeatherForecastEntry]


class OpenWeatherOneCallHourlyEntry(_BaseModel):
    dt: int


class OpenWeatherOneCallDailyEntry(_BaseModel):
    dt: int


class OpenWeatherOneCallPayload(_BaseModel):
    lat: float
    lon: float
    hourly: List[OpenWeatherOneCallHourlyEntry] = []
    daily: List[OpenWeatherOneCallDailyEntry] = []


class TomorrowLocation(_BaseModel):
    lat: float
    lon: float
    name: Optional[str] = None


class TomorrowRealtimeData(_BaseModel):
    time: str
    values: Dict[str, Any]


class TomorrowRealtimePayload(_BaseModel):
    location: TomorrowLocation
    data: TomorrowRealtimeData


class TomorrowTimelineInterval(_BaseModel):
    time: str
    values: Dict[str, Any]


class TomorrowForecastPayload(_BaseModel):
    location: TomorrowLocation
    timelines: Dict[str, List[TomorrowTimelineInterval]]


class MscGeometry(_BaseModel):
    coordinates: List[float]


class MscFeaturePayload(_BaseModel):
    geometry: MscGeometry
    properties: Dict[str, Any]


class MscFeatureCollectionPayload(_BaseModel):
    features: List[MscFeaturePayload]


class RdpsPrognosFeaturePayload(_BaseModel):
    geometry: MscGeometry
    properties: Dict[str, Any]


class RdpsPrognosFeatureCollectionPayload(_BaseModel):
    features: List[RdpsPrognosFeaturePayload]


class AmbientDevice(_BaseModel):
    lastData: Dict[str, Any]


class AmbientObservationPayload(RootModel[List[AmbientDevice]]):
    pass


class AccuGeoPosition(_BaseModel):
    Latitude: float
    Longitude: float


class AccuLocationPayload(_BaseModel):
    Key: str
    GeoPosition: AccuGeoPosition


class AccuCurrentCondition(_BaseModel):
    EpochTime: Optional[int] = None
    LocalObservationDateTime: Optional[str] = None


class AccuCurrentConditionsPayload(RootModel[List[AccuCurrentCondition]]):
    pass


class AccuHourlyEntry(_BaseModel):
    EpochDateTime: Optional[int] = None
    DateTime: Optional[str] = None


class AccuHourlyForecastPayload(RootModel[List[AccuHourlyEntry]]):
    pass


class AccuDailyEntry(_BaseModel):
    EpochDate: Optional[int] = None
    Date: Optional[str] = None


class AccuDailyForecastPayload(_BaseModel):
    DailyForecasts: List[AccuDailyEntry]
