from datetime import datetime
from typing import Literal, TypedDict

from pydantic import Field

from app.schemas.product import AccommodationRecommendation, TransportComparison
from app.schemas.travel import (
    POI,
    Constraints,
    Evidence,
    FlightOption,
    Itinerary,
    RailOption,
    RouteOption,
    Schema,
    ValidationResult,
    WeatherRecord,
)

RunStatus = Literal[
    "queued", "running", "needs_clarification", "completed", "partial", "conflict", "failed", "cancelled"
]


class TraceEvent(Schema):
    sequence: int
    run_id: str
    itinerary_version: int
    agent: str
    status: Literal["pending", "running", "succeeded", "failed", "skipped"]
    summary: str
    timestamp: datetime
    duration_ms: int = 0
    evidence_ids: list[str] = Field(default_factory=list)


class AgentState(TypedDict, total=False):
    flight_options: list[FlightOption]
    transport_comparisons: list[TransportComparison]
    accommodation: list[AccommodationRecommendation]
    accommodation_reselections: int
    session_id: str
    memory_preferences: dict
    user_query: str
    origin: str | None
    destinations: list[str]
    travel_dates: list
    total_budget: int | None
    preferences: list[str]
    constraints: Constraints
    transport_options: list[RailOption]
    poi_candidates: list[POI]
    weather_data: list[WeatherRecord]
    route_data: list[RouteOption]
    draft_itinerary: Itinerary | None
    validation_result: ValidationResult | None
    validation_history: list[dict]
    replanning_count: int
    agent_trace: list[TraceEvent]
    final_itinerary: Itinerary | None
    routing_plan: list[str]
    questions: list[str]
    status: RunStatus
    evidence: dict[str, Evidence]
    city_schedule: list[str]
    issue_signature: str
    stop_reason: str | None
