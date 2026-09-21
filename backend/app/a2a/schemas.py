from datetime import date
from typing import Literal

from pydantic import Field

from app.harness.runtime import RuntimeEvent
from app.schemas.travel import (
    POI,
    Constraints,
    Evidence,
    RailOption,
    RouteOption,
    Schema,
    WeatherRecord,
)


class SpecialistState(Schema):
    constraints: Constraints
    city_schedule: list[str] = Field(max_length=7)
    travel_dates: list[date] = Field(max_length=7)
    evidence: dict[str, Evidence] = Field(default_factory=dict)


class SpecialistRequest(Schema):
    state: SpecialistState
    source_mode: Literal["live", "fixture"]
    simulated_rain: bool = False
    tool_allowance: int = Field(ge=1, le=200)
    external_allowance: int = Field(ge=0, le=500)
    remaining_seconds: float = Field(gt=0, le=600)


class SpecialistDelta(Schema):
    transport_options: list[RailOption] | None = None
    poi_candidates: list[POI] | None = None
    weather_data: list[WeatherRecord] | None = None
    route_data: list[RouteOption] | None = None
    evidence: dict[str, Evidence] = Field(default_factory=dict)


class ProviderState(Schema):
    state: Literal["LIVE", "MOCK", "DATASET", "PENDING", "FAILED", "UNCONFIGURED"]
    model: str | None = None
    error_code: str | None = None


class ToolObservation(Schema):
    tool: Literal["rail_search", "amap_poi", "amap_weather", "amap_route", "amap_distance"]
    status: str = Field(max_length=64, pattern=r"^[A-Za-z_]+$")
    cached: bool


class SpecialistReply(Schema):
    delta: SpecialistDelta
    tool_calls: int = Field(ge=0, le=200)
    external_calls: int = Field(ge=0, le=500)
    providers: dict[str, ProviderState]
    mcp_state: Literal["PENDING", "CONNECTED", "FALLBACK"]
    mcp_tools: list[str]
    runtime_events: list[RuntimeEvent] = Field(default_factory=list)
    tool_observations: list[ToolObservation] = Field(default_factory=list, max_length=200)
