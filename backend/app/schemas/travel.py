from datetime import date, time, timedelta
from typing import Generic, Literal, TypeVar

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.core.errors import SafeError


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Evidence(Schema):
    id: str
    provider: str
    source_kind: Literal["mock", "dataset", "live", "estimate"]
    source: str | None = None
    retrieved_at: AwareDatetime
    valid_for: list[date] = Field(default_factory=list)
    stale: bool = False
    notes: str = ""


T = TypeVar("T")


class ToolResult(Schema, Generic[T]):
    status: Literal["ok", "empty", "unavailable", "error"] = "ok"
    data: T | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    error: SafeError | None = None


class Coordinates(Schema):
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    system: Literal["GCJ-02"] = "GCJ-02"


class Place(Schema):
    id: str
    name: str
    city: str
    coordinates: Coordinates | None = None


class FlightQuery(Schema):
    origin: str = Field(min_length=1, max_length=40)
    destination: str = Field(min_length=1, max_length=40)
    date: date
    passengers: int = Field(default=1, ge=1, le=6)


class FlightOption(Schema):
    id: str
    flight_no: str
    origin_airport: Place
    destination_airport: Place
    departure_time: AwareDatetime
    arrival_time: AwareDatetime
    duration_minutes: int = Field(gt=0)
    price: int | None = Field(default=None, ge=0)
    source: str
    evidence_id: str
    availability_status: Literal["unknown", "available", "unavailable"] = "unknown"
    provider_mode: Literal["DATASET", "LIVE"] = "DATASET"

    @model_validator(mode="after")
    def consistent_time(self):
        if abs((self.arrival_time - self.departure_time).total_seconds() / 60 - self.duration_minutes) > 1:
            raise ValueError("inconsistent flight timing")
        return self


class RailQuery(Schema):
    origin: str = Field(min_length=1, max_length=40)
    destination: str = Field(min_length=1, max_length=40)
    date: date
    passengers: int = Field(default=1, ge=1, le=6)
    seat_class: str = "二等座"
    allow_transfer: bool = True


class RailLeg(Schema):
    train_no: str
    origin_station: Place
    destination_station: Place
    departure_time: AwareDatetime
    arrival_time: AwareDatetime
    duration: int = Field(gt=0)
    train_type: str = "高铁"
    price: int | None = Field(default=None, ge=0, description="CNY fen per passenger")
    availability: Literal["unknown", "available", "unavailable"] = "unknown"
    seat_class: str = "二等座"
    evidence_id: str

    @model_validator(mode="after")
    def check_duration(self) -> "RailLeg":
        if (
            self.arrival_time <= self.departure_time
            or abs((self.arrival_time - self.departure_time).total_seconds() / 60 - self.duration) > 1
        ):
            raise ValueError("inconsistent rail timing")
        return self


class RailOption(Schema):
    id: str
    legs: list[RailLeg] = Field(min_length=1, max_length=3)
    direct: bool = True
    transfer_minutes: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent_transfer(self) -> "RailOption":
        if self.direct != (len(self.legs) == 1):
            raise ValueError("inconsistent direct flag")
        if len(self.transfer_minutes) != len(self.legs) - 1:
            raise ValueError("missing transfer information")
        return self


class POIQuery(Schema):
    city: str = Field(min_length=1, max_length=40)
    keywords: str = Field(default="", max_length=100)
    category: Literal["attraction", "restaurant"] = "attraction"
    limit: int = Field(default=12, ge=1, le=20)


class POI(Place):
    category: Literal["attraction", "restaurant"] = "attraction"
    environment: Literal["indoor", "outdoor", "unknown"] = "unknown"
    visit_minutes: int = Field(default=90, gt=0)
    ticket_price: int | None = Field(default=None, ge=0)
    opening_start: time | None = None
    opening_end: time | None = None
    evidence_id: str
    tags: list[str] = Field(default_factory=list)


class RouteQuery(Schema):
    origin: Place
    destination: Place
    mode: Literal["walk", "drive", "transit"] = "transit"
    departure_time: AwareDatetime | None = None


class RouteOption(Schema):
    id: str
    origin: Place
    destination: Place
    mode: Literal["walk", "drive", "transit"]
    duration: int = Field(gt=0)
    distance: int = Field(ge=0)
    price: int | None = Field(default=None, ge=0)
    evidence_id: str


class DistanceQuery(Schema):
    origin: Coordinates
    destination: Coordinates
    mode: Literal["straight", "drive", "walk"] = "straight"


class DistanceResult(Schema):
    meters: int = Field(ge=0)
    methodology: Literal["straight", "drive", "walk"]
    evidence_id: str


class WeatherQuery(Schema):
    city: str = Field(min_length=1, max_length=40)
    dates: list[date] = Field(min_length=1, max_length=7)


class WeatherRecord(Schema):
    city: str
    date: date
    condition: str
    severity: Literal["normal", "adverse", "severe", "unknown"]
    temperature: str | None = None
    min_temperature: float | None = None
    max_temperature: float | None = None
    precipitation: float | None = Field(default=None, ge=0)
    precipitation_probability: float | None = Field(default=None, ge=0, le=100)
    evidence_id: str


class Constraints(Schema):
    travel_pace: Literal["relaxed", "balanced", "compact"] = "balanced"
    transport_preference: Literal["high_speed_rail", "flight", "no_preference"] = "no_preference"
    transport_mode: Literal["rail", "flight"] | None = None
    avoid_early_departure: bool = False
    walking_tolerance: Literal["low", "medium", "high"] = "medium"
    accommodation_preferences: list[str] = Field(default_factory=list, max_length=3)
    indoor_days: list[int] = Field(default_factory=list, max_length=7)
    recommend_hotels: bool = False
    compare_transport: bool = False
    arrival_deadline: time | None = None

    origin: str | None = None
    destinations: list[str] = Field(default_factory=list, max_length=4)
    start_date: date | None = None
    end_date: date | None = None
    days: int | None = Field(default=None, ge=1, le=7)
    total_budget: int | None = Field(default=None, ge=0, description="CNY fen for entire party")
    preferences: list[str] = Field(default_factory=list)
    passengers: int = Field(default=1, ge=1, le=6)
    max_attractions: int = Field(default=3, ge=1, le=6)
    max_local_minutes: int = Field(default=120, ge=1, le=480)
    station_buffer: int = Field(default=45, ge=15, le=180)
    transfer_buffer: int = Field(default=30, ge=15, le=180)
    activity_start: time = time(9)
    activity_end: time = time(20)
    max_walk_minutes: int | None = Field(default=None, ge=1, le=240)
    assumptions: list[str] = Field(
        default_factory=lambda: ["默认 1 位成人；费用为人民币估算；不自动添加返程。"]
    )

    @model_validator(mode="after")
    def check_dates(self) -> "Constraints":
        if self.start_date and self.end_date:
            count = (self.end_date - self.start_date).days + 1
            if count < 1 or count > 7 or (self.days is not None and self.days != count):
                raise ValueError("inconsistent dates")
        if len(set(self.destinations)) != len(self.destinations):
            raise ValueError("duplicate destinations")
        return self

    @property
    def dates(self) -> list[date]:
        if not self.start_date or not self.days:
            return []
        return [self.start_date + timedelta(days=n) for n in range(self.days)]


class DayWeather(Schema):
    city: str
    forecast_date: date
    weather_condition: str | None = None
    min_temperature: float | None = None
    max_temperature: float | None = None
    precipitation: float | None = None
    precipitation_probability: float | None = None
    source: str = "unavailable"
    status: Literal["live", "pending", "simulated"] = "pending"
    evidence_id: str | None = None


class RestBreak(Schema):
    label: str
    start: AwareDatetime
    end: AwareDatetime


class Activity(Schema):
    poi: POI
    start: AwareDatetime
    end: AwareDatetime
    time_period: Literal["morning", "afternoon", "evening"] = "morning"
    estimated_duration: int | None = None
    route_from_previous: RouteOption | None = None
    travel_minutes: int | None = None
    source: str = "unknown"
    optional: bool = False
    notes: list[str] = Field(default_factory=list)


class LocalLeg(Schema):
    route: RouteOption
    departure: AwareDatetime
    arrival: AwareDatetime


CostCategory = Literal["inter_city", "local_transport", "accommodation", "tickets", "food", "reserve"]


class CostItem(Schema):
    id: str
    category: CostCategory
    amount: int | None = Field(default=None, ge=0)
    label: str
    source: Literal["mock", "dataset", "live", "estimate"] = "estimate"


class CostSummary(Schema):
    categories: dict[str, int] = Field(default_factory=dict)
    estimated_total: int = 0
    known_cost: int = 0
    estimated_cost: int = 0
    unknown_cost_items: list[str] = Field(default_factory=list)
    budget_limit: int | None = None
    unknown_items: list[str] = Field(default_factory=list)
    budget: int | None = None
    delta: int | None = None


class DayPlan(Schema):
    day: int
    date: date
    city: str
    origin_city: str
    rail: RailOption | None = None
    flight: FlightOption | None = None
    activities: list[Activity] = Field(default_factory=list)
    local_legs: list[LocalLeg] = Field(default_factory=list)
    costs: list[CostItem] = Field(default_factory=list)
    estimated_cost: int = 0
    weather: DayWeather | None = None
    breaks: list[RestBreak] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class Itinerary(Schema):
    version: int = 1
    title: str = "江南慢行 · 城市之间"
    days: list[DayPlan]
    costs: CostSummary = Field(default_factory=CostSummary)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class Issue(Schema):
    type: str
    severity: Literal["info", "warning", "error"]
    status: Literal["confirmed", "unverified", "informational"]
    blocking: bool = False
    activity_id: str | None = None
    target: str | None = None
    source: str = "validator"
    evidence: dict = Field(default_factory=dict)
    message: str
    suggestion: str
    day: int | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    observed: str | None = None
    allowed: str | None = None

    @model_validator(mode="after")
    def blocking_requires_proof(self):
        if self.blocking and (self.status != "confirmed" or self.severity != "error"):
            raise ValueError("blocking requires a confirmed error")
        if self.status == "unverified" and self.severity != "warning":
            raise ValueError("unverified issues must be warnings")
        if self.status == "informational" and self.severity != "info":
            raise ValueError("informational issues must be info")
        return self


class ValidationResult(Schema):
    valid: bool
    confirmed_count: int = 0
    blocking_confirmed_count: int = 0
    unverified_count: int = 0
    informational_count: int = 0
    issues: list[Issue] = Field(default_factory=list)
    checked_constraints: list[str] = Field(default_factory=list)
    unverified_checks: list[str] = Field(default_factory=list)
    passed_checks: int = 0
    total_checks: int = 0
