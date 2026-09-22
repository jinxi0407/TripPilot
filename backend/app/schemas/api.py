from typing import Literal

from pydantic import Field

from app.core.errors import SafeError
from app.graph.state import RunStatus, TraceEvent
from app.schemas.product import AccommodationRecommendation, TransportComparison, TravelPreferences
from app.schemas.travel import Constraints, Evidence, Itinerary, Schema, ValidationResult


class PlanRequest(Schema):
    session_id: str | None = Field(default=None, max_length=64)
    remember_preferences: bool = False
    travel_preferences: TravelPreferences | None = None
    product_features: bool = False
    query: str = Field(min_length=1, max_length=4000)
    constraints: Constraints | None = None
    mode: Literal["auto", "fixture", "live"] = "auto"
    demo: bool = False
    scenario: Literal["normal", "rain", "outage", "transport"] = "normal"


class ClarificationRequest(Schema):
    expected_revision: int = Field(ge=1)
    answers: Constraints


class RevisionRequest(Schema):
    reason: Literal["weather", "transport", "budget", "route"]
    query: str | None = Field(default=None, max_length=4000)
    constraints: Constraints | None = None


class RunMetrics(Schema):
    agent_steps: dict[str, int]
    tool_attempts: int = Field(ge=0, le=200)
    model_attempts: int = Field(ge=0, le=100)
    tokens: int | None = None
    replanning_count: int = Field(ge=0, le=5)


class PlanResponse(Schema):
    session_id: str | None = None
    memory: dict = Field(default_factory=dict)
    accommodation: list[AccommodationRecommendation] = Field(default_factory=list)
    transport_comparisons: list[TransportComparison] = Field(default_factory=list)
    run_id: str
    task_id: str
    status: RunStatus
    revision: int
    itinerary_version: int
    parent_id: str | None
    mode: Literal["fixture", "qwen"]
    provider_status: dict[str, "ProviderStatus"] = Field(default_factory=dict)
    runtime_status: dict = Field(default_factory=dict)
    simulated_rain: bool = False
    poll_url: str
    constraints: Constraints | None
    needs_clarification: bool = False
    missing_fields: list[str] = Field(default_factory=list)
    questions: list[str]
    itinerary: Itinerary | None
    validation: ValidationResult | None
    validation_history: list[dict] = Field(default_factory=list)
    trace: list[TraceEvent]
    evidence: list[Evidence]
    metrics: RunMetrics
    error: SafeError | None


class HealthResponse(Schema):
    main_backend: str = "ONLINE"
    qwen: dict = Field(default_factory=dict)
    amap: dict = Field(default_factory=dict)
    rail: dict = Field(default_factory=dict)
    mcp: dict = Field(default_factory=dict)
    a2a_transport: dict = Field(default_factory=dict)
    a2a_local: dict = Field(default_factory=dict)
    harness: dict = Field(default_factory=dict)
    status: Literal["ok"]
    service: Literal["TripPilot"]
    version: str
    mode: Literal["fixture", "live"]
    providers: dict[str, bool | str]
    provider_status: dict[str, "ProviderStatus"] = Field(default_factory=dict)
    runtime_status: dict = Field(default_factory=dict)


class ProviderStatus(Schema):
    state: Literal["LIVE", "MOCK", "DATASET", "PENDING", "FAILED", "UNCONFIGURED"]
    model: str | None = None
    error_code: str | None = None
