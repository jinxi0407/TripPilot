from datetime import date

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.providers.amap import AmapProvider
from app.providers.fixtures import STATIONS, city_pois
from app.providers.flight import DatasetFlightProvider, RealFlightProvider
from app.providers.hotel import AmapHotelProvider
from app.providers.rail import DatasetRailProvider
from app.schemas.product import HotelCandidate, HotelQuery
from app.schemas.travel import Constraints, FlightOption, FlightQuery, RailQuery
from app.services.accommodation import hotel_score, research_accommodation
from app.services.engine import create_context, execute
from app.services.transport_comparison import compare_transport, time_estimate


async def test_amap_hotel_reuses_existing_client_and_has_no_fake_price():
    seen = []

    async def respond(request):
        seen.append(request.url.path)
        assert request.url.params["types"] == "100000"
        return httpx.Response(
            200,
            json={
                "status": "1",
                "pois": [
                    {
                        "id": "hotel1",
                        "name": "真实酒店POI",
                        "location": "120.15,30.25",
                        "address": "某街道",
                        "adname": "西湖区",
                    }
                ],
            },
        )

    local = AmapProvider("test-key", transport=httpx.MockTransport(respond))
    r = await AmapHotelProvider(local).search(HotelQuery(city="杭州"))
    assert seen == ["/v3/place/text"]
    assert r.data[0].source == "amap_live" and r.data[0].realtime_price is None
    assert r.data[0].availability_status == "unknown" and r.evidence[0].source == "amap_live"


async def test_hotel_missing_optional_fields():
    local = AmapProvider(
        "test",
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200, json={"status": "1", "pois": [{"id": "h", "name": "酒店", "address": [], "adname": []}]}
            )
        ),
    )
    h = (await AmapHotelProvider(local).search(HotelQuery(city="南京"))).data[0]
    assert h.coordinates is h.address is h.district is None
    with pytest.raises(ValidationError):
        HotelCandidate(**{**h.model_dump(), "realtime_price": 100})


async def test_hotel_timeout_is_controlled():
    context = create_context(Settings(), mode="fixture", scenario="outage")
    result = await context.registry.call("Local Travel", "search_hotels", {"city": "杭州"})
    assert result.status == "error" and result.error.code == "TIMEOUT"
    assert context.budget.tools == 2


async def test_hotel_area_scoring_station_and_route():
    context = create_context(Settings(), mode="fixture")
    state = {
        "constraints": Constraints(
            origin="杭州",
            destinations=["杭州"],
            days=2,
            start_date=date(2026, 10, 10),
            recommend_hotels=True,
            accommodation_preferences=["near_metro"],
        ),
        "city_schedule": ["杭州", "杭州"],
        "poi_candidates": city_pois("杭州"),
        "evidence": {},
    }
    recommendations, _ = await research_accommodation(state, context)
    r = recommendations[0]
    assert r.main_poi_ids and r.reasons and r.station_id == STATIONS["杭州"].id
    assert r.candidates[0].route and r.candidates[0].station_route
    assert hotel_score(r.candidates[0], city_pois("杭州")) < hotel_score(r.candidates[-1], city_pois("杭州"))
    assert "需另行确认" in r.reasons[-1]


async def test_flight_dataset_schema_and_provenance():
    r = await DatasetFlightProvider().search(
        FlightQuery(origin="北京", destination="上海", date=date(2026, 10, 10))
    )
    assert len(r.data) == 2 and r.evidence[0].source_kind == "dataset"
    assert all(f.provider_mode == "DATASET" and f.availability_status == "unknown" for f in r.data)
    assert (
        await RealFlightProvider().search(
            FlightQuery(origin="北京", destination="上海", date=date(2026, 10, 10))
        )
    ).status == "unavailable"


async def test_flight_missing_price_and_invalid_timing():
    f = (
        await DatasetFlightProvider().search(
            FlightQuery(origin="北京", destination="上海", date=date(2026, 10, 10))
        )
    ).data[0]
    assert FlightOption.model_validate({**f.model_dump(), "price": None}).price is None
    with pytest.raises(ValidationError):
        FlightOption.model_validate({**f.model_dump(), "duration_minutes": 1})


async def test_rail_flight_door_to_door_preferences_and_unavailable():
    query = {"origin": "北京", "destination": "上海", "date": date(2026, 10, 10)}
    rails = await DatasetRailProvider().search(RailQuery(**query))
    flights = await DatasetFlightProvider().search(FlightQuery(**query))
    constraints = Constraints(avoid_early_departure=True, transport_preference="high_speed_rail")
    result = compare_transport(
        "北京",
        "上海",
        1,
        rails.data,
        flights.data,
        constraints,
        {e.id: e for e in rails.evidence + flights.evidence},
    )
    assert {c.mode for c in result.candidates} == {"rail", "flight"}
    assert all(c.estimate.estimated_total_minutes == c.estimate.calculated_total for c in result.candidates)
    assert result.recommended_id and any("偏好" in x for c in result.candidates for x in c.reasons)
    flights.data[0].availability_status = "unavailable"
    result = compare_transport("北京", "上海", 1, rails.data, flights.data, constraints, {})
    assert flights.data[0].id not in {c.id for c in result.candidates}
    assert time_estimate(130, "flight").estimated_total_minutes == 370


async def test_flight_selected_in_itinerary_and_critic():
    context = create_context(Settings(rail_provider="dataset"), mode="fixture")
    state = await execute(
        {
            "user_query": "2026-10-10 从北京到上海两天，预算4000元。",
            "constraints": Constraints(transport_mode="flight", compare_transport=True),
        },
        context,
    )
    assert state.get("final_itinerary")
    assert state["final_itinerary"].days[0].flight
    assert not any(i.type == "MISSING_TRANSPORT" for i in state["validation_result"].issues)


async def test_product_hotel_full_graph_and_budget():
    context = create_context(Settings(rail_provider="dataset"), mode="fixture", demo=True)
    state = await execute(
        {
            "user_query": "我想从上海出发，用5天游玩杭州、南京和苏州。预算4000元。",
            "constraints": Constraints(recommend_hotels=True, compare_transport=True),
        },
        context,
    )
    assert len(state["accommodation"]) == 3
    assert len(state["transport_comparisons"]) == 3
    assert context.budget.tools <= context.runtime.policy.max_tool_calls
    assert state.get("final_itinerary")


async def test_accommodation_critic_reselection_is_bounded():
    from app.agents.critic import critique
    from app.schemas.travel import Coordinates

    context = create_context(Settings(rail_provider="dataset"), mode="fixture")
    state = await execute(
        {"user_query": "2026-10-10 杭州两天，预算3000元", "constraints": Constraints(recommend_hotels=True)},
        context,
    )
    assert state["final_itinerary"]
    recommendation = state["accommodation"][0]
    first = next(h for h in recommendation.candidates if h.id == recommendation.selected_hotel_id)
    first.coordinates = Coordinates(longitude=121.2, latitude=31.2)
    first.route = first.route.model_copy(update={"duration": 90})
    first.station_route = first.station_route.model_copy(update={"duration": 100})
    update = await critique(
        {**state, "draft_itinerary": state["final_itinerary"], "replanning_count": 0, "issue_signature": ""},
        context,
    )
    issues = {i.type for i in update["validation_result"].issues}
    assert "HOTEL_TOO_FAR" in issues
    assert sum(i.type == "HOTEL_TOO_FAR" for i in update["validation_result"].issues) >= 3
    assert update["accommodation_reselections"] == 1 and update["replanning_count"] == 1
    assert update["accommodation"][0].selected_hotel_id != first.id


def test_door_to_door_rejects_inconsistent_and_keeps_unknown():
    from app.schemas.product import TravelTimeEstimate

    with pytest.raises(ValidationError):
        TravelTimeEstimate(
            local_access_minutes=30,
            recommended_buffer_minutes=45,
            scheduled_duration_minutes=60,
            arrival_transfer_minutes=30,
            estimated_total_minutes=1,
        )
    unknown = TravelTimeEstimate(
        recommended_buffer_minutes=45, scheduled_duration_minutes=60, access_source="unknown"
    )
    assert unknown.estimated_total_minutes is None
