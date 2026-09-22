from datetime import datetime, time, timedelta
from itertools import pairwise

from pydantic import Field

from app.core.errors import ControlledError
from app.graph.state import AgentState
from app.providers.fixtures import TZ
from app.schemas.travel import (
    Activity,
    CostItem,
    DayPlan,
    Itinerary,
    LocalLeg,
    Place,
    RestBreak,
    RouteQuery,
    Schema,
)
from app.services.costing import reconcile
from app.services.day_planning import city_day_pois, night_place, route_mode
from app.services.day_weather import day_weather


class DaySelection(Schema):
    day: int = Field(ge=1, le=7)
    poi_ids: list[str] = Field(max_length=6)
    rail_id: str | None = None
    flight_id: str | None = None


def default_selections(state: AgentState) -> list[DaySelection]:
    """Deterministic fixture policy. Live Qwen is free to choose among the same evidenced IDs."""
    constraints = state["constraints"]
    issues = (
        {i.type for i in state.get("validation_result").issues} if state.get("validation_result") else set()
    )
    rain_repair = state.get("replanning_count", 0) > 0 and any(
        w.severity == "severe" for w in state.get("weather_data", [])
    )
    economy = (
        state.get("replanning_count", 0) > 0
        and constraints.total_budget is not None
        and (
            state.get("draft_itinerary") is not None
            and state["draft_itinerary"].costs.estimated_total > constraints.total_budget
            or "BUDGET_EXCEEDED" in issues
        )
    )
    selections = []
    live_pois = {eid for eid, e in state.get("evidence", {}).items() if e.source == "amap_live"}
    previous = constraints.origin
    for index, (city, day) in enumerate(zip(state["city_schedule"], constraints.dates)):
        candidates = [p for p in state.get("poi_candidates", []) if p.city == city]
        same_as_previous = index > 0 and state["city_schedule"][index - 1] == city
        if rain_repair or index + 1 in constraints.indoor_days:
            selected = [p for p in candidates if p.environment == "indoor"][:2]
        elif same_as_previous:
            selected = [candidates[3]] if len(candidates) > 3 else candidates[:1]
            selected += [p for p in candidates if "夜景" in p.tags][-1:]
        else:
            selected = candidates[:2]
        if (
            (
                candidates
                and any(p.evidence_id in live_pois for p in candidates)
                and not rain_repair
                and index + 1 not in constraints.indoor_days
            )
            or constraints.travel_pace == "compact"
            and not rain_repair
            and index + 1 not in constraints.indoor_days
        ):
            selected = city_day_pois(
                candidates,
                constraints,
                state["city_schedule"][:index].count(city),
                routes=state.get("route_data", []),
            )
        if economy:
            affordable = [
                p
                for p in candidates
                if p.ticket_price == 0 and (not rain_repair or p.environment == "indoor")
            ][:2]
            # Unknown live ticket prices are not zero; retain a useful draft for budget conflict reporting.
            if affordable:
                selected = affordable
        options = (
            [
                r
                for r in state.get("transport_options", [])
                if r.legs[0].origin_station.city == previous
                and r.legs[-1].destination_station.city == city
                and r.legs[0].departure_time.date() == day
                and all(l.availability != "unavailable" for l in r.legs)
            ]
            if city != previous
            else []
        )
        rail = min(options, key=lambda r: r.legs[0].departure_time) if options else None
        if (
            rail
            and rail.legs[-1].arrival_time.hour >= 13
            and not rain_repair
            and index + 1 not in constraints.indoor_days
        ):
            selected = (
                [p for p in candidates if p.environment == "indoor"][:1]
                + [p for p in candidates if "夜景" in p.tags][-1:]
            )[:2]
        if "ROUTE_INEFFICIENCY" in issues and len(selected) > 1:
            route_lookup = {(r.origin.id, r.destination.id): r.duration for r in state.get("route_data", [])}
            forward = [route_lookup.get((a.id, b.id)) for a, b in pairwise(selected)]
            reverse = [route_lookup.get((b.id, a.id)) for a, b in pairwise(selected)]
            if all(v is not None for v in forward + reverse) and sum(reverse) < sum(forward):
                selected = list(reversed(selected))
        if constraints.avoid_early_departure:
            late = [r for r in options if r.legs[0].departure_time.hour >= 9]
            if late:
                rail = min(late, key=lambda r: r.legs[0].departure_time)
        flight_id = None
        comparison = next((c for c in state.get("transport_comparisons", []) if c.day == index + 1), None)
        if comparison and comparison.recommended_id:
            chosen = next((c for c in comparison.candidates if c.id == comparison.recommended_id), None)
            if chosen and chosen.mode == "flight":
                flight_id = chosen.id
                rail = None
            elif chosen:
                rail = next((r for r in options if r.id == chosen.id), rail)
        if constraints.transport_mode == "flight" and not flight_id:
            rail = None
        selected = selected[: constraints.max_attractions]
        selections.append(
            DaySelection(
                day=index + 1,
                poi_ids=[p.id for p in selected],
                rail_id=rail.id if rail else None,
                flight_id=flight_id,
            )
        )
        previous = city
    return selections


def as_place(value) -> Place:
    return Place.model_validate(value.model_dump(include={"id", "name", "city", "coordinates"}))


def assemble(
    state: AgentState, selections: list[DaySelection], version: int
) -> tuple[Itinerary, list[RouteQuery]]:
    constraints = state["constraints"]
    if sorted(s.day for s in selections) != list(range(1, len(state["city_schedule"]) + 1)):
        raise ControlledError("INVALID_OUTPUT")
    pois = {p.id: p for p in state.get("poi_candidates", [])}
    flights = {f.id: f for f in state.get("flight_options", [])}
    rails = {r.id: r for r in state.get("transport_options", [])}
    live_routing = any(e.source == "amap_live" for e in state.get("evidence", {}).values())
    routes = {(r.origin.id, r.destination.id, r.mode): r for r in state.get("route_data", [])}
    issues = (
        {i.type for i in state.get("validation_result").issues} if state.get("validation_result") else set()
    )
    economy = "BUDGET_EXCEEDED" in issues
    itinerary = Itinerary(
        version=version,
        days=[],
        assumptions=list(constraints.assumptions)
        + [
            "住宿为预算占位，不包含酒店预订；餐饮与备用金为估算。",
            "首日从出发火车站开始；未提供住址和酒店位置，不含其接驳。",
        ],
    )
    missing = []
    previous_city = constraints.origin
    previous_poi = None
    source_by_id = {e.id: e.source_kind for e in state.get("evidence", {}).values()}
    evidenced_defaults = {s.day: s for s in default_selections(state)}
    for selection in sorted(selections, key=lambda s: s.day):
        if not selection.rail_id and not selection.flight_id:
            fallback = evidenced_defaults.get(selection.day)
            if fallback:
                selection = selection.model_copy(
                    update={"rail_id": fallback.rail_id, "flight_id": fallback.flight_id}
                )
        index = selection.day - 1
        day = constraints.dates[index]
        city = state["city_schedule"][index]
        selected = []
        for pid in selection.poi_ids:
            if pid not in pois or pois[pid].city != city:
                raise ControlledError("INVALID_OUTPUT")
            selected.append(pois[pid])
        rail = rails.get(selection.rail_id) if selection.rail_id else None
        if selection.rail_id and rail is None:
            raise ControlledError("INVALID_OUTPUT")
        flight = flights.get(selection.flight_id) if selection.flight_id else None
        if selection.flight_id and (not flight or rail):
            raise ControlledError("INVALID_OUTPUT")
        if rail and (
            rail.legs[0].origin_station.city != previous_city
            or rail.legs[-1].destination_station.city != city
            or rail.legs[0].departure_time.date() != day
        ):
            raise ControlledError("INVALID_OUTPUT")
        if flight and (
            flight.origin_airport.city != previous_city
            or flight.destination_airport.city != city
            or flight.departure_time.date() != day
        ):
            raise ControlledError("INVALID_OUTPUT")
        result = DayPlan(
            day=index + 1,
            date=day,
            city=city,
            origin_city=previous_city or city,
            rail=rail,
            flight=flight,
            weather=day_weather(state, city, day),
        )
        clock = datetime.combine(day, constraints.activity_start, TZ)
        if constraints.avoid_early_departure:
            clock = max(clock, datetime.combine(day, time(9, 30), TZ))
        for hour, label in [(12, "午餐 / 休息"), (18, "晚餐 / 休息")]:
            start = datetime.combine(day, time(hour), TZ)
            result.breaks.append(RestBreak(label=label, start=start, end=start + timedelta(hours=1)))
        result.notes.append("活动时长为游览估算，餐食与休息已预留；开放时间需临行确认。")
        if rail:
            if (
                rail.legs[0].origin_station.city != previous_city
                or rail.legs[-1].destination_station.city != city
            ):
                raise ControlledError("INVALID_OUTPUT")
            if rail.legs[0].departure_time.date() != day:
                raise ControlledError("INVALID_OUTPUT")
            for leg_index, leg in enumerate(rail.legs):
                result.costs.append(
                    CostItem(
                        id=f"{index}-rail-{leg_index}",
                        category="inter_city",
                        amount=leg.price * constraints.passengers if leg.price is not None else None,
                        label=f"{leg.origin_station.name} → {leg.destination_station.name}",
                        source=source_by_id.get(leg.evidence_id, "estimate"),
                    )
                )
            if previous_poi:
                q = RouteQuery(origin=as_place(previous_poi), destination=rail.legs[0].origin_station)
                route = routes.get((q.origin.id, q.destination.id, q.mode))
                if route:
                    departure = min(
                        clock,
                        rail.legs[0].departure_time
                        - timedelta(minutes=constraints.station_buffer + route.duration),
                    )
                    arrival = departure + timedelta(minutes=route.duration)
                    result.local_legs.append(LocalLeg(route=route, departure=departure, arrival=arrival))
                else:
                    missing.append(q)
            clock = max(clock, rail.legs[-1].arrival_time + timedelta(minutes=15))
            last_place = rail.legs[-1].destination_station
        elif flight:
            result.costs.append(
                CostItem(
                    id=f"{index}-flight",
                    category="inter_city",
                    amount=flight.price * constraints.passengers if flight.price is not None else None,
                    label=flight.flight_no,
                    source=source_by_id.get(flight.evidence_id, "estimate"),
                )
            )
            clock = max(clock, flight.arrival_time + timedelta(minutes=30))
            last_place = flight.destination_airport
        else:
            last_place = None
        for position, poi in enumerate(selected):
            original_clock = clock
            previous_leg_count = len(result.local_legs)
            route = None
            if last_place:
                q = RouteQuery(
                    origin=as_place(last_place),
                    destination=as_place(poi),
                    mode=route_mode(last_place, poi, constraints) if live_routing else "transit",
                )
                route = routes.get((q.origin.id, q.destination.id, q.mode))
                if route:
                    arrival = clock + timedelta(minutes=route.duration)
                    result.local_legs.append(LocalLeg(route=route, departure=clock, arrival=arrival))
                    clock = arrival
                else:
                    missing.append(q)
            if poi.opening_start:
                clock = max(clock, datetime.combine(day, poi.opening_start, TZ))
            if "夜景" in constraints.preferences and night_place(poi) and position == len(selected) - 1:
                clock = max(clock, datetime.combine(day, time(19), TZ))
            # Move meal buffers past evidenced rail/flight/local travel; a 12:50 arrival
            # must reserve a full hour instead of claiming lunch already happened at 12:00.
            travel_intervals = [(leg.departure, leg.arrival) for leg in result.local_legs]
            if rail:
                travel_intervals += [(leg.departure_time, leg.arrival_time) for leg in rail.legs]
            if flight:
                travel_intervals.append((flight.departure_time, flight.arrival_time))
            for rest in result.breaks:
                for departure, arrival in sorted(travel_intervals):
                    if rest.start < arrival and rest.end > departure:
                        rest.start = arrival
                        rest.end = arrival + timedelta(hours=1)
                if clock < rest.end and clock + timedelta(minutes=poi.visit_minutes) > rest.start:
                    clock = rest.end
            end = clock + timedelta(minutes=poi.visit_minutes)
            closing = min(
                datetime.combine(day, constraints.activity_end, TZ),
                datetime.combine(day, poi.opening_end, TZ)
                if poi.opening_end
                else datetime.combine(day, constraints.activity_end, TZ),
            )
            local_minutes = sum(leg.route.duration for leg in result.local_legs)
            # A closed attraction is never scheduled, even as the first item. Keep an
            # evidenced first access leg for Critic to report unavoidable transit conflicts.
            if end > closing or (result.activities and local_minutes > constraints.max_local_minutes):
                result.notes.append(f"{poi.name}未排入：开放/活动时间窗或交通预算不足。")
                result.local_legs = result.local_legs[:previous_leg_count]
                clock = original_clock
                continue
            source = state.get("evidence", {}).get(poi.evidence_id)
            result.activities.append(
                Activity(
                    poi=poi,
                    start=clock,
                    end=end,
                    time_period="evening"
                    if clock.hour >= 18
                    else "afternoon"
                    if clock.hour >= 12
                    else "morning",
                    estimated_duration=poi.visit_minutes,
                    route_from_previous=route,
                    travel_minutes=route.duration if route else None,
                    source=(source.source or source.source_kind) if source else "unknown",
                    optional=night_place(poi),
                    notes=["游览时长为估算"],
                )
            )
            result.costs.append(
                CostItem(
                    id=f"{index}-ticket-{poi.id}",
                    category="tickets",
                    amount=poi.ticket_price * constraints.passengers
                    if poi.ticket_price is not None
                    else None,
                    label=poi.name,
                    source=source_by_id.get(poi.evidence_id, "estimate"),
                )
            )
            clock = end + timedelta(minutes=15)
            last_place = poi
        for ri, leg in enumerate(result.local_legs):
            result.costs.append(
                CostItem(
                    id=f"{index}-local-{ri}",
                    category="local_transport",
                    amount=leg.route.price * constraints.passengers if leg.route.price is not None else None,
                    label=f"{leg.route.origin.name} → {leg.route.destination.name}",
                    source=source_by_id.get(leg.route.evidence_id, "estimate"),
                )
            )
        for category, amount, label in [
            (
                "accommodation",
                (12000 if economy else 20000) if index < len(selections) - 1 else 0,
                "住宿预算",
            ),
            ("food", 6000 if economy else 10000, "餐饮估算"),
            ("reserve", 2000 if economy else 3000, "备用金"),
        ]:
            result.costs.append(
                CostItem(
                    id=f"{index}-{category}",
                    category=category,
                    amount=amount * constraints.passengers,
                    label=label,
                )
            )
        itinerary.days.append(result)
        previous_city = city
        previous_poi = result.activities[-1].poi if result.activities else None
    itinerary.evidence_ids = list(state.get("evidence", {}))
    try:
        itinerary.costs = reconcile(itinerary, constraints.total_budget)
    except ValueError:
        raise ControlledError("INVALID_OUTPUT") from None
    if missing:
        itinerary.warnings.append("部分市内路线尚无证据，不能确认完整可行性。")
    return itinerary, missing
