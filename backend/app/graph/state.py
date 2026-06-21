"""LangGraph state definitions."""

from typing import Any, List, Optional, TypedDict

from app.models.schemas import TripPlan, TripRequest


class TripGraphState(TypedDict, total=False):
    request: TripRequest
    messages: List[Any]
    attractions_raw: Any
    weather_raw: Any
    hotels_raw: Any
    draft_plan: Any
    trip_plan: Optional[TripPlan]
    errors: List[str]
