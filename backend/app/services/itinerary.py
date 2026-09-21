from datetime import datetime, time, timedelta
from itertools import pairwise

from pydantic import Field

from app.core.errors import ControlledError
from app.graph.state import AgentState
from app.providers.fixtures import TZ
from app.schemas.travel import Activity, CostItem, DayPlan, Itinerary, LocalLeg, Place, RouteQuery, Schema
from app.services.costing import reconcile


class DaySelection(Schema):
    day: int = Field(ge=1, le=7)
    poi_ids: list[str] = Field(max_length=6)
    rail_id: str | None = None


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
        if rain_repair:
            selected = [p for p in candidates if p.environment == "indoor"][:2]
        elif same_as_previous:
            selected = [candidates[3]] if len(candidates) > 3 else candidates[:1]
            selected += [p for p in candidates if "夜景" in p.tags][-1:]
        else:
            selected = candidates[:2]
        if candidates and any(p.evidence_id in live_pois for p in candidates) and not rain_repair:
            # Real transit includes station access; preserve a relaxed arrival day and avoid repeated POIs.
            selected = [candidates[-1] if same_as_previous else candidates[0]]
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
        if rail and rail.legs[-1].arrival_time.hour >= 13 and not rain_repair:
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
        selections.append(
            DaySelection(day=index + 1, poi_ids=[p.id for p in selected], rail_id=rail.id if rail else None)
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
    rails = {r.id: r for r in state.get("transport_options", [])}
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
    for selection in sorted(selections, key=lambda s: s.day):
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
        result = DayPlan(day=index + 1, date=day, city=city, origin_city=previous_city or city, rail=rail)
        clock = datetime.combine(day, constraints.activity_start, TZ)
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
        else:
            last_place = None
        for position, poi in enumerate(selected):
            if last_place:
                q = RouteQuery(origin=as_place(last_place), destination=as_place(poi))
                route = routes.get((q.origin.id, q.destination.id, q.mode))
                if route:
                    arrival = clock + timedelta(minutes=route.duration)
                    result.local_legs.append(LocalLeg(route=route, departure=clock, arrival=arrival))
                    clock = arrival
                else:
                    missing.append(q)
            if poi.opening_start:
                clock = max(clock, datetime.combine(day, poi.opening_start, TZ))
            if "夜景" in constraints.preferences and "夜景" in poi.tags and position == len(selected) - 1:
                clock = max(clock, datetime.combine(day, time(19), TZ))
            end = clock + timedelta(minutes=poi.visit_minutes)
            result.activities.append(Activity(poi=poi, start=clock, end=end))
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
        previous_poi = selected[-1] if selected else None
    itinerary.evidence_ids = list(state.get("evidence", {}))
    try:
        itinerary.costs = reconcile(itinerary, constraints.total_budget)
    except ValueError:
        raise ControlledError("INVALID_OUTPUT") from None
    if missing:
        itinerary.warnings.append("部分市内路线尚无证据，不能确认完整可行性。")
    return itinerary, missing
