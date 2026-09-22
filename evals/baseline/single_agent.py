"""One Qwen tool-using planner, no specialist calls, Critic or replanning loop."""

from typing import Any, Literal

from app.agents.supervisor import distribute_cities, parse_fixture
from app.harness.runtime import TOOL_NAMES
from app.mcp.schemas import CONTRACTS
from app.persistence.memory import (
    extract_preferences,
    normalize_default_window,
    preference_constraints,
)
from app.providers.fixtures import STATIONS
from app.schemas.product import (
    AccommodationRecommendation,
    HotelQuery,
    TravelPreferences,
)
from app.schemas.travel import (
    Constraints,
    DistanceQuery,
    FlightQuery,
    POIQuery,
    RailQuery,
    RouteQuery,
    Schema,
    WeatherQuery,
)
from app.services.accommodation import center_of, hotel_score
from app.services.itinerary import DaySelection, as_place, assemble, default_selections
from app.services.model_client import MockModelClient, structured_call
from app.services.transport_comparison import compare_transport
from pydantic import Field


class ToolCall(Schema):
    tool: str
    arguments: dict[str, Any]


class SingleDecision(Schema):
    kind: Literal["actions", "final", "conflict"]
    calls: list[ToolCall] = Field(default_factory=list, max_length=12)
    selections: list[DaySelection] = Field(default_factory=list, max_length=7)


async def execute_single(state, context):
    existing = state.get("constraints")
    if isinstance(context.model, MockModelClient):
        extracted = Constraints.model_validate(
            parse_fixture(state["user_query"], context.now.date())
        )
    else:
        extracted = await structured_call(
            context.model,
            {
                "task": "single_agent_intake",
                "query": state["user_query"],
                "provided_constraints": existing.model_dump(mode="json")
                if existing
                else {},
                "preferences": context.memory_preferences,
                "instruction": "提取明确约束，预算单位分；不虚构日期。",
            },
            Constraints,
            context.budget,
            context.usage,
        )
    data = extracted.model_dump()
    data.update(
        preference_constraints(
            TravelPreferences.model_validate(context.memory_preferences)
        )
    )
    if existing:
        data.update(existing.model_dump(exclude_unset=True))
    data.update(
        preference_constraints(
            TravelPreferences.model_validate(extract_preferences(state["user_query"]))
        )
    )
    data = normalize_default_window(data, existing, state["user_query"])
    constraints = Constraints.model_validate(data)
    if not constraints.origin or not constraints.destinations or not constraints.dates:
        return {**state, "constraints": constraints, "status": "needs_clarification"}
    working = {
        **state,
        "constraints": constraints,
        "city_schedule": distribute_cities(constraints),
        "travel_dates": constraints.dates,
        "transport_options": [],
        "flight_options": [],
        "poi_candidates": [],
        "weather_data": [],
        "route_data": [],
        "transport_comparisons": [],
        "accommodation": [],
        "evidence": {},
        "replanning_count": 0,
        "routing_plan": [],
    }
    queue = []
    hotels = {}
    completed = set()
    observations = []

    def enqueue(name, query):
        args = query.model_dump(mode="json")
        key = name + query.model_dump_json()
        if key not in completed:
            queue.append((key, {"tool": name, "arguments": args}))

    origin = constraints.origin
    for day, city in enumerate(working["city_schedule"]):
        if city != origin:
            enqueue(
                "search_rail",
                RailQuery(
                    origin=origin,
                    destination=city,
                    date=constraints.dates[day],
                    passengers=constraints.passengers,
                ),
            )
            if constraints.compare_transport or constraints.transport_mode == "flight":
                enqueue(
                    "search_flights",
                    FlightQuery(
                        origin=origin,
                        destination=city,
                        date=constraints.dates[day],
                        passengers=constraints.passengers,
                    ),
                )
        origin = city
    for city in dict.fromkeys(working["city_schedule"]):
        enqueue("search_poi", POIQuery(city=city))
        enqueue(
            "get_weather",
            WeatherQuery(
                city=city,
                dates=[
                    d
                    for d, c in zip(constraints.dates, working["city_schedule"])
                    if c == city
                ],
            ),
        )
    stage = 0
    draft = None
    for step in range(context.runtime.policy.max_react_steps):
        context.runtime.step("Single Agent")
        context.steps["Single Agent"] = step + 1
        if not queue and stage == 0:
            stage = 1
            if constraints.recommend_hotels:
                for city in dict.fromkeys(working["city_schedule"]):
                    enqueue(
                        "search_hotels",
                        HotelQuery(
                            city=city,
                            center=center_of(
                                [p for p in working["poi_candidates"] if p.city == city]
                            ),
                        ),
                    )
        if not queue and stage == 1:
            stage = 2
            for city, items in hotels.items():
                pois = [p for p in working["poi_candidates"] if p.city == city]
                ranked = sorted(
                    items,
                    key=lambda h: hotel_score(
                        h,
                        pois,
                        STATIONS.get(city),
                        constraints.accommodation_preferences,
                    ),
                )
                if ranked and pois:
                    h = ranked[0]
                    center = center_of(pois)
                    if h.coordinates and center:
                        enqueue(
                            "calculate_distance",
                            DistanceQuery(origin=h.coordinates, destination=center),
                        )
                        enqueue(
                            "plan_route",
                            RouteQuery(
                                origin=as_place(h), destination=as_place(pois[0])
                            ),
                        )
                        if city in STATIONS:
                            enqueue(
                                "plan_route",
                                RouteQuery(
                                    origin=as_place(h), destination=STATIONS[city]
                                ),
                            )
        origin = constraints.origin
        working["transport_comparisons"] = []
        if constraints.compare_transport or constraints.transport_mode == "flight":
            for day, city in enumerate(working["city_schedule"]):
                if city != origin:
                    rails = [
                        r
                        for r in working["transport_options"]
                        if r.legs[0].origin_station.city == origin
                        and r.legs[-1].destination_station.city == city
                        and r.legs[0].departure_time.date() == constraints.dates[day]
                    ]
                    flights = [
                        f
                        for f in working["flight_options"]
                        if f.origin_airport.city == origin
                        and f.destination_airport.city == city
                        and f.departure_time.date() == constraints.dates[day]
                    ]
                    working["transport_comparisons"].append(
                        compare_transport(
                            origin,
                            city,
                            day + 1,
                            rails,
                            flights,
                            constraints,
                            working["evidence"],
                        )
                    )
                origin = city
        selections = default_selections(working)
        draft, missing = assemble(working, selections, context.version)
        if not queue and stage == 2:
            for q in missing:
                enqueue("plan_route", q)
        packet = {
            k: [x.model_dump(mode="json") for x in working[k]]
            for k in [
                "transport_options",
                "flight_options",
                "poi_candidates",
                "weather_data",
                "route_data",
                "transport_comparisons",
            ]
        }
        if isinstance(context.model, MockModelClient):
            decision = (
                SingleDecision(
                    kind="actions", calls=[ToolCall(**item) for _, item in queue[:12]]
                )
                if queue
                else SingleDecision(kind="final", selections=selections)
            )
        else:
            decision = await structured_call(
                context.model,
                {
                    "task": "single_agent_travel_planning",
                    "query": state["user_query"],
                    "constraints": constraints.model_dump(mode="json"),
                    "evidence": packet,
                    "hotel_candidates": {
                        c: [h.model_dump(mode="json") for h in hs]
                        for c, hs in hotels.items()
                    },
                    "available_tools": [
                        "search_rail",
                        "search_flights",
                        "search_poi",
                        "search_hotels",
                        "get_weather",
                        "calculate_distance",
                        "plan_route",
                    ],
                    "tool_schemas": {
                        name: contract[0].model_json_schema()
                        for name, contract in CONTRACTS.items()
                    },
                    "tool_observations": observations[-12:],
                    "pending_queries": [item for _, item in queue[:12]],
                    "suggested_selections": [s.model_dump() for s in selections],
                    "draft_costs": draft.costs.model_dump(),
                    "remaining_steps": context.runtime.policy.max_react_steps - step,
                    "instruction": "你是唯一旅行智能体，可通过actions批量调用同样旅行工具。不依赖其他智能体或独立Critic。pending_queries是尚待查询的证据，非空优先复制调用。空时可采用suggested_selections或自行选择已知ID，检查用户预算、天气、时间和偏好；严重天气仅选室内。无可满足方案返回conflict及当前selections，不能虚构可行性。只输出决策JSON，无隐藏推理。",
                },
                SingleDecision,
                context.budget,
                context.usage,
            )
        if decision.kind != "actions":
            draft, _ = assemble(working, decision.selections, context.version)
            working.update(
                draft_itinerary=draft,
                final_itinerary=draft,
                status="conflict" if decision.kind == "conflict" else "completed",
            )
            break
        for call in decision.calls:
            name = TOOL_NAMES.get(call.tool, call.tool)
            result = await context.registry.call("Travel Planner", name, call.arguments)
            observations.append(
                {
                    "tool": name,
                    "status": result.status,
                    "error_code": result.error.code if result.error else None,
                }
            )
            working["evidence"].update({e.id: e for e in result.evidence})
            # Failed arguments are observations, not an unhandled second validation.
            if result.status == "error":
                continue
            if name in CONTRACTS:
                query = CONTRACTS[name][0].model_validate(call.arguments)
                key = name + query.model_dump_json()
                completed.add(key)
                # Compare normalized schemas, including omitted optional defaults.
                queue = [
                    (queued_key, item)
                    for queued_key, item in queue
                    if queued_key != key
                ]
            field = {
                "search_rail": "transport_options",
                "search_flights": "flight_options",
                "search_poi": "poi_candidates",
                "get_weather": "weather_data",
                "plan_route": "route_data",
            }.get(name)
            if field:
                working[field].extend(result.data or [])
            if name == "search_hotels":
                hotels[call.arguments["city"]] = result.data or []
    else:
        working.update(
            status="failed",
            stop_reason="MAX_STEPS",
            draft_itinerary=draft,
            final_itinerary=draft,
        )
    for city, items in hotels.items():
        pois = (
            [a.poi for d in draft.days if d.city == city for a in d.activities]
            if draft
            else []
        )
        ranked = sorted(
            items,
            key=lambda h: hotel_score(
                h, pois, STATIONS.get(city), constraints.accommodation_preferences
            ),
        )
        for h in ranked:
            h.route = next(
                (
                    r
                    for r in working["route_data"]
                    if r.origin.id == h.id and r.destination.id in {p.id for p in pois}
                ),
                None,
            )
            h.station_route = next(
                (
                    r
                    for r in working["route_data"]
                    if r.origin.id == h.id
                    and city in STATIONS
                    and r.destination.id == STATIONS[city].id
                ),
                None,
            )
        working["accommodation"].append(
            AccommodationRecommendation(
                city=city,
                days=[
                    i + 1 for i, c in enumerate(working["city_schedule"]) if c == city
                ],
                recommended_area=(" / ".join(p.name for p in pois[:2]) or city)
                + "周边活动区",
                reasons=["按同一POI坐标距离和车站便利性排序"],
                candidates=ranked,
                selected_hotel_id=ranked[0].id if ranked else None,
                main_poi_ids=[p.id for p in pois],
                station_id=STATIONS[city].id if city in STATIONS else None,
            )
        )
    context.emit(
        "Single Agent",
        "succeeded" if working.get("status") != "failed" else "failed",
        "单智能体完成工具查询与行程提交；未运行独立Critic或重规划",
    )
    return working
