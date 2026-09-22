from typing import Literal

from pydantic import Field, model_validator

from app.schemas.travel import Coordinates, Place, RouteOption, Schema


class TravelPreferences(Schema):
    travel_pace: Literal["relaxed", "balanced", "compact"] | None = None
    interests: list[Literal["history", "night_view", "nature"]] = Field(default_factory=list)
    transport_preference: Literal["high_speed_rail", "flight", "no_preference"] | None = None
    budget_level: Literal["low", "medium", "high"] | None = None
    avoid_early_departure: bool | None = None
    walking_tolerance: Literal["low", "medium", "high"] | None = None
    accommodation_preferences: list[Literal["near_metro", "close_to_main_pois", "near_station"]] = Field(
        default_factory=list
    )


class PreferenceRequest(Schema):
    preferences: TravelPreferences = Field(default_factory=TravelPreferences)
    query: str | None = Field(default=None, max_length=1000)
    remember_preferences: bool = False


class HotelQuery(Schema):
    city: str = Field(min_length=1, max_length=40)
    keywords: str = Field(default="酒店", max_length=80)
    center: Coordinates | None = None
    limit: int = Field(default=3, ge=1, le=5)


class HotelCandidate(Place):
    hotel_name: str
    address: str | None = None
    district: str | None = None
    source: Literal["amap_live", "hotel_fixture"]
    evidence_id: str
    distance_meters: int | None = Field(default=None, ge=0)
    distance_kind: Literal["estimated_straight", "provider", "unknown"] = "unknown"
    route: RouteOption | None = None
    station_route: RouteOption | None = None
    metro_access: Literal["unknown", "verified"] = "unknown"
    realtime_price: None = None
    availability_status: Literal["unknown"] = "unknown"


class AccommodationRecommendation(Schema):
    city: str
    days: list[int]
    recommended_area: str
    reasons: list[str]
    candidates: list[HotelCandidate]
    selected_hotel_id: str | None = None
    main_poi_ids: list[str]
    station_id: str | None = None
    reselected: bool = False
    disclaimer: str = "酒店候选来自 POI；实时房价和房态需在 OTA 平台确认，未接入预订。"


class TravelTimeEstimate(Schema):
    local_access_minutes: int | None = Field(default=None, ge=0)
    recommended_buffer_minutes: int = Field(ge=0)
    scheduled_duration_minutes: int = Field(gt=0)
    arrival_transfer_minutes: int | None = Field(default=None, ge=0)
    estimated_total_minutes: int | None = Field(default=None, ge=0)
    access_source: Literal["estimated", "unknown", "provider"] = "estimated"
    assumptions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent_total(self):
        if self.estimated_total_minutes != self.calculated_total:
            raise ValueError("door-to-door total must equal the components; unknown remains unknown")
        return self

    @property
    def calculated_total(self):
        if self.local_access_minutes is None or self.arrival_transfer_minutes is None:
            return None
        return (
            self.local_access_minutes
            + self.recommended_buffer_minutes
            + self.scheduled_duration_minutes
            + self.arrival_transfer_minutes
        )


class TransportCandidate(Schema):
    id: str
    mode: Literal["rail", "flight"]
    provider_mode: Literal["DATASET", "MOCK", "LIVE"]
    source: str
    cost: int | None = Field(default=None, ge=0)
    transfers: int = Field(ge=0)
    departure: str
    arrival: str
    estimate: TravelTimeEstimate
    score: float
    reasons: list[str]


class TransportComparison(Schema):
    origin: str
    destination: str
    day: int
    candidates: list[TransportCandidate]
    recommended_id: str | None = None
    recommendation: str
