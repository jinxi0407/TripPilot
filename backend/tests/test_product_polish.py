from datetime import date, datetime, time

import pytest
from test_supervisor import context

from app.agents.critic import validate_itinerary
from app.agents.supervisor import DEMO_QUERY, supervise
from app.providers.amap import AmapProvider
from app.providers.fixtures import TZ, city_pois
from app.schemas.travel import Constraints, Evidence, RouteOption, WeatherQuery, WeatherRecord
from app.services.day_planning import city_day_pois, cluster_order, night_place
from app.services.day_weather import day_weather
from app.services.itinerary import DaySelection, as_place, assemble, default_selections

DAY = date(2026, 10, 10)


def sample(pace="relaxed", count=2):
    pois = city_pois("杭州")
    constraints = Constraints(
        origin="杭州",
        destinations=["杭州"],
        start_date=DAY,
        days=1,
        travel_pace=pace,
        max_attractions=4 if pace == "compact" else 3,
        preferences=["历史", "夜景"],
        activity_end=time(21, 30),
    )
    evidence = Evidence(
        id="poi-杭州",
        provider="Amap",
        source="amap_live",
        source_kind="live",
        retrieved_at=datetime(2026, 10, 10, tzinfo=TZ),
        valid_for=[DAY],
    )
    routes = [
        RouteOption(
            id=f"{a.id}-{b.id}",
            origin=as_place(a),
            destination=as_place(b),
            mode=mode,
            duration=15,
            distance=1000,
            price=200,
            evidence_id="route",
        )
        for mode in ("walk", "transit")
        for a in pois
        for b in pois
        if a.id != b.id
    ]
    state = {
        "constraints": constraints,
        "city_schedule": ["杭州"],
        "poi_candidates": pois,
        "route_data": routes,
        "weather_data": [],
        "evidence": {evidence.id: evidence},
    }
    selected = city_day_pois(pois, constraints, 0, routes=routes)[:count]
    draft, _ = assemble(state, [DaySelection(day=1, poi_ids=[p.id for p in selected])], 1)
    return state, draft


async def test_clarification_original_query_with_date_does_not_block():
    state = await supervise({"user_query": DEMO_QUERY, "constraints": Constraints(start_date=DAY)}, context())
    assert state["status"] == "running" and not state["questions"]
    assert state["constraints"].days == 5
    assert state["constraints"].end_date == date(2026, 10, 14)


async def test_omitted_structured_fields_recover_only_explicit_facts():
    ctx = context()
    from app.services.model_client import ModelReply

    class OmittedClient:
        name = "qwen"

        async def complete(self, payload, schema):
            assert payload["session_constraints"] == {"start_date": "2026-10-10", "recommend_hotels": True}
            return ModelReply(content="{}")

    ctx.model = OmittedClient()
    result = await supervise(
        {"user_query": DEMO_QUERY, "constraints": Constraints(start_date=DAY, recommend_hotels=True)}, ctx
    )
    assert result["constraints"].origin == "上海"
    assert result["routing_plan"] == ["Transport", "Local Travel"]


@pytest.mark.parametrize("pace,minimum", [("relaxed", 2), ("compact", 3)])
def test_full_day_density_and_evidenced_ids(pace, minimum):
    state, _ = sample(pace, 4)
    selections = default_selections(state)
    draft, _ = assemble(state, selections, 1)
    assert len(draft.days[0].activities) >= minimum
    assert {a.poi.id for a in draft.days[0].activities} <= {p.id for p in state["poi_candidates"]}
    assert not {"DAY_TOO_EMPTY", "DAY_TOO_DENSE"} & {
        i.type for i in validate_itinerary(draft, state["constraints"], state).issues
    }


def test_night_preference_and_meal_buffers():
    _state, draft = sample()
    day = draft.days[0]
    assert night_place(day.activities[-1].poi)
    assert day.activities[-1].start.hour >= 18
    for activity in day.activities:
        assert activity.estimated_duration
        assert not any(activity.start < b.end and activity.end > b.start for b in day.breaks)
    assert day.activities[-1].travel_minutes == 15


def test_critic_detects_empty_full_day_but_exempts_transfer_rain_and_long_visit():
    state, draft = sample(count=1)
    kinds = lambda: {i.type for i in validate_itinerary(draft, state["constraints"], state).issues}
    assert "DAY_TOO_EMPTY" in kinds()
    draft.days[0].origin_city = "上海"
    assert "DAY_TOO_EMPTY" not in kinds()
    draft.days[0].origin_city = "杭州"
    state["weather_data"] = [
        WeatherRecord(city="杭州", date=DAY, condition="暴雨", severity="severe", evidence_id="w")
    ]
    state["evidence"]["w"] = next(iter(state["evidence"].values())).model_copy(update={"id": "w"})
    assert "DAY_TOO_EMPTY" not in kinds()
    state["weather_data"] = []
    from datetime import timedelta

    draft.days[0].activities[0].end = draft.days[0].activities[0].start + timedelta(hours=5)
    assert "DAY_TOO_EMPTY" not in kinds()


def test_critic_dense_transit_and_preference_checks():
    state, draft = sample(count=2)
    state["constraints"].max_attractions = 1
    state["constraints"].max_local_minutes = 1
    issues = {i.type for i in validate_itinerary(draft, state["constraints"], state).issues}
    assert {"DAY_TOO_DENSE", "EXCESSIVE_TRANSIT"} <= issues
    for a in draft.days[0].activities:
        a.poi.tags = []
        a.poi.name = "普通地点"
    issues = {i.type for i in validate_itinerary(draft, state["constraints"], state).issues}
    assert "NO_PREFERENCE_ALIGNMENT" in issues


def test_cluster_uses_actual_route_and_limits_excessive_transit():
    state, _ = sample()
    pois = state["poi_candidates"][:2]
    for r in state["route_data"]:
        if r.origin.id == pois[0].id and r.destination.id == pois[1].id:
            r.duration = 200
    ordered = cluster_order(pois, state["route_data"])
    assert ordered[0].id == pois[1].id
    draft, _ = assemble(state, [DaySelection(day=1, poi_ids=[p.id for p in pois])], 1)
    assert len(draft.days[0].activities) == 1
    assert any("交通预算不足" in n for n in draft.days[0].notes)


def test_indoor_repair_and_late_arrival_not_quantity_filler():
    state, _ = sample()
    chosen = city_day_pois(state["poi_candidates"], state["constraints"], 0, indoor=True)
    assert chosen and all(p.environment == "indoor" for p in chosen)
    state["constraints"].activity_start = time(16)
    state["constraints"].activity_end = time(17)
    draft, _ = assemble(state, [DaySelection(day=1, poi_ids=[p.id for p in chosen])], 1)
    assert len(draft.days[0].activities) <= 1


@pytest.mark.parametrize(
    "source,stale,matching,status",
    [
        ("amap_live", False, True, "live"),
        ("amap_live", True, True, "pending"),
        ("amap_live", False, False, "pending"),
        ("weather_simulation", False, True, "simulated"),
    ],
)
def test_weather_provenance_dates_and_no_fabricated_numbers(source, stale, matching, status):
    state, _ = sample()
    e = Evidence(
        id="weather",
        provider="Amap",
        source=source,
        source_kind="live" if source == "amap_live" else "mock",
        retrieved_at=datetime(2026, 10, 10, tzinfo=TZ),
        valid_for=[DAY],
        stale=stale,
    )
    state["evidence"][e.id] = e
    state["weather_data"] = [
        WeatherRecord(
            city="杭州",
            date=DAY if matching else date(2026, 10, 11),
            condition="晴",
            severity="normal",
            min_temperature=18,
            max_temperature=26,
            evidence_id=e.id,
        )
    ]
    w = day_weather(state, "杭州", DAY)
    assert w.status == status
    assert (w.min_temperature, w.max_temperature) == ((18, 26) if status == "live" else (None, None))
    assert day_weather(state, "南京", DAY).status == "pending"


async def test_amap_weather_keeps_actual_night_and_day_temperatures():
    provider = AmapProvider("unit-test-not-a-key")

    async def respond(path, params):
        assert path == "weather/weatherInfo" and params["extensions"] == "all"
        return {
            "forecasts": [
                {"casts": [{"date": str(DAY), "dayweather": "晴", "daytemp": "26", "nighttemp": "18"}]}
            ]
        }

    provider._get = respond
    result = await provider.weather(WeatherQuery(city="杭州", dates=[DAY]))
    assert (result.data[0].min_temperature, result.data[0].max_temperature) == (18, 26)
    assert result.data[0].precipitation_probability is None
    assert (await provider.weather(WeatherQuery(city="杭州", dates=[date(2026, 11, 1)]))).data == []


def test_meal_buffer_moves_after_travel_and_keeps_a_full_hour():
    state, _ = sample()
    for route in state["route_data"]:
        route.duration = 120
    draft, _ = assemble(state, default_selections(state), 1)
    day = draft.days[0]
    lunch = day.breaks[0]
    assert (lunch.end - lunch.start).total_seconds() == 3600
    assert all(not (lunch.start < leg.arrival and lunch.end > leg.departure) for leg in day.local_legs)
    assert all(not (a.start < lunch.end and a.end > lunch.start) for a in day.activities)


def test_critic_cluster_warning_requires_provider_route_evidence():
    state, _ = sample()
    state["constraints"].max_local_minutes = 480
    first, second = state["poi_candidates"][:2]
    for route in state["route_data"]:
        if route.origin.id == first.id and route.destination.id == second.id:
            route.duration = 100
    draft, _ = assemble(state, [DaySelection(day=1, poi_ids=[first.id, second.id])], 1)
    issues = {i.type for i in validate_itinerary(draft, state["constraints"], state).issues}
    assert {"ROUTE_INEFFICIENCY", "POI_CLUSTER_INEFFICIENT"} <= issues
