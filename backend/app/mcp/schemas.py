from typing import Generic, Literal, TypeVar

from pydantic import Field

from app.schemas.product import HotelCandidate, HotelQuery
from app.schemas.travel import (
    POI,
    DistanceQuery,
    DistanceResult,
    FlightOption,
    FlightQuery,
    POIQuery,
    RailOption,
    RailQuery,
    RouteOption,
    RouteQuery,
    Schema,
    ToolResult,
    WeatherQuery,
    WeatherRecord,
)

T = TypeVar("T")


class MCPReply(Schema, Generic[T]):
    result: T
    provider_state: Literal["LIVE", "MOCK", "DATASET", "FAILED", "PENDING", "UNCONFIGURED"]
    external_calls: int = Field(ge=0, le=1)


CONTRACTS = {
    "search_flights": (FlightQuery, ToolResult[list[FlightOption]], "search"),
    "search_hotels": (HotelQuery, ToolResult[list[HotelCandidate]], "search"),
    "search_rail": (RailQuery, ToolResult[list[RailOption]], "search"),
    "search_poi": (POIQuery, ToolResult[list[POI]], "pois"),
    "get_weather": (WeatherQuery, ToolResult[list[WeatherRecord]], "weather"),
    "calculate_distance": (DistanceQuery, ToolResult[list[DistanceResult]], "distance"),
    "plan_route": (RouteQuery, ToolResult[list[RouteOption]], "route"),
}
