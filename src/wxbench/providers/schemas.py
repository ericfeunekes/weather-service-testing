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


class AmbientHistoryPayload(RootModel[List[Dict[str, Any]]]):
    pass


class EcowittRealtimePayload(_BaseModel):
    data: Dict[str, Any]
    time: Optional[Any] = None
    code: Optional[int] = None
    msg: Optional[str] = None


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


class WeatherKitMetadata(_BaseModel):
    latitude: float
    longitude: float


class WeatherKitCurrentWeather(_BaseModel):
    metadata: WeatherKitMetadata
    asOf: str


class WeatherKitHourWeatherConditions(_BaseModel):
    forecastStart: str


class WeatherKitHourlyForecast(_BaseModel):
    metadata: WeatherKitMetadata
    hours: List[WeatherKitHourWeatherConditions]


class WeatherKitDayWeatherConditions(_BaseModel):
    forecastStart: str
    forecastEnd: Optional[str] = None


class WeatherKitDailyForecast(_BaseModel):
    metadata: WeatherKitMetadata
    days: List[WeatherKitDayWeatherConditions]


class WeatherKitForecastMinute(_BaseModel):
    startTime: str


class WeatherKitForecastPeriodSummary(_BaseModel):
    startTime: str
    endTime: Optional[str] = None
    condition: Optional[str] = None


class WeatherKitNextHourForecast(_BaseModel):
    metadata: Optional[WeatherKitMetadata] = None
    forecastStart: str
    forecastEnd: str
    minutes: List[WeatherKitForecastMinute]
    summary: List[WeatherKitForecastPeriodSummary]


class WeatherKitAlertSummary(_BaseModel):
    id: str
    issuedTime: str
    effectiveTime: str
    expireTime: str
    description: str
    severity: str
    certainty: str
    source: str
    countryCode: str
    areaId: Optional[str] = None
    areaName: Optional[str] = None
    detailsUrl: Optional[str] = None
    eventOnsetTime: Optional[str] = None
    eventEndTime: Optional[str] = None
    urgency: Optional[str] = None
    responses: Optional[List[str]] = None


class WeatherKitAlertCollection(_BaseModel):
    metadata: Optional[WeatherKitMetadata] = None
    alerts: List[WeatherKitAlertSummary]
    detailsUrl: Optional[str] = None


class WeatherKitWeatherPayload(_BaseModel):
    currentWeather: Optional[WeatherKitCurrentWeather] = None
    forecastHourly: Optional[WeatherKitHourlyForecast] = None
    forecastDaily: Optional[WeatherKitDailyForecast] = None
    forecastNextHour: Optional[WeatherKitNextHourForecast] = None
    weatherAlerts: Optional[WeatherKitAlertCollection] = None
