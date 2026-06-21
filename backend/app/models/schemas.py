"""Shared request and response models."""

from typing import List, Optional, Union

from pydantic import BaseModel, Field, field_validator


class TripRequest(BaseModel):
    city: str = Field(..., description="目的地城市", examples=["北京"])
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD", examples=["2026-07-01"])
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD", examples=["2026-07-03"])
    travel_days: int = Field(..., ge=1, le=30, description="旅行天数")
    transportation: str = Field(..., description="交通方式")
    accommodation: str = Field(..., description="住宿偏好")
    preferences: List[str] = Field(default_factory=list, description="旅行偏好标签")
    free_text_input: Optional[str] = Field(default="", description="额外要求")


class POISearchRequest(BaseModel):
    keywords: str = Field(..., description="搜索关键词")
    city: str = Field(..., description="城市")
    citylimit: bool = Field(default=True, description="是否限制在城市范围内")


class RouteRequest(BaseModel):
    origin_address: str = Field(..., description="起点地址")
    destination_address: str = Field(..., description="终点地址")
    origin_city: Optional[str] = Field(default=None, description="起点城市")
    destination_city: Optional[str] = Field(default=None, description="终点城市")
    route_type: str = Field(default="walking", description="walking/driving/transit")


class Location(BaseModel):
    longitude: float
    latitude: float


class Attraction(BaseModel):
    name: str
    address: str
    location: Location
    visit_duration: int
    description: str
    category: Optional[str] = "景点"
    rating: Optional[float] = None
    photos: Optional[List[str]] = Field(default_factory=list)
    poi_id: Optional[str] = ""
    image_url: Optional[str] = None
    ticket_price: int = 0


class Meal(BaseModel):
    type: str
    name: str
    address: Optional[str] = None
    location: Optional[Location] = None
    description: Optional[str] = None
    estimated_cost: int = 0


class Hotel(BaseModel):
    name: str
    address: str = ""
    location: Optional[Location] = None
    price_range: str = ""
    rating: str = ""
    distance: str = ""
    type: str = ""
    estimated_cost: int = 0


class DayPlan(BaseModel):
    date: str
    day_index: int
    description: str
    transportation: str
    accommodation: str
    hotel: Optional[Hotel] = None
    attractions: List[Attraction] = Field(default_factory=list)
    meals: List[Meal] = Field(default_factory=list)


class WeatherInfo(BaseModel):
    date: str
    day_weather: str = ""
    night_weather: str = ""
    day_temp: Union[int, str] = 0
    night_temp: Union[int, str] = 0
    wind_direction: str = ""
    wind_power: str = ""

    @field_validator("day_temp", "night_temp", mode="before")
    @classmethod
    def parse_temperature(cls, value):
        if isinstance(value, str):
            cleaned = value.replace("°C", "").replace("℃", "").replace("°", "").strip()
            try:
                return int(cleaned)
            except ValueError:
                return 0
        return value


class Budget(BaseModel):
    total_attractions: int = 0
    total_hotels: int = 0
    total_meals: int = 0
    total_transportation: int = 0
    total: int = 0


class TripPlan(BaseModel):
    city: str
    start_date: str
    end_date: str
    days: List[DayPlan]
    weather_info: List[WeatherInfo] = Field(default_factory=list)
    overall_suggestions: str
    budget: Optional[Budget] = None


class TripPlanResponse(BaseModel):
    success: bool
    message: str = ""
    data: Optional[TripPlan] = None


class POIInfo(BaseModel):
    id: str
    name: str
    type: str = ""
    address: str = ""
    location: Location
    tel: Optional[str] = None


class POISearchResponse(BaseModel):
    success: bool
    message: str = ""
    data: List[POIInfo] = Field(default_factory=list)


class RouteInfo(BaseModel):
    distance: float
    duration: int
    route_type: str
    description: str


class RouteResponse(BaseModel):
    success: bool
    message: str = ""
    data: Optional[RouteInfo] = None


class WeatherResponse(BaseModel):
    success: bool
    message: str = ""
    data: List[WeatherInfo] = Field(default_factory=list)


class POIDetailResponse(BaseModel):
    success: bool
    message: str = ""
    data: Optional[dict] = None


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    error_code: Optional[str] = None
