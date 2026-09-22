from app.graph.state import AgentState
from app.schemas.travel import FlightQuery, RailQuery
from app.services.context import RunContext
from app.services.transport_comparison import compare_transport


async def research_transport(state: AgentState, context: RunContext) -> dict:
    options, evidence = [], dict(state.get("evidence", {}))
    flights, comparisons = [], []
    origin = state["constraints"].origin
    for day, city in enumerate(state["city_schedule"]):
        if city != origin:
            context.emit("Rail Search", "running", f"正在查询{origin}至{city}高铁")
            result = await context.registry.call(
                "Transport",
                "rail_search",
                RailQuery(
                    origin=origin,
                    destination=city,
                    date=state["travel_dates"][day],
                    passengers=state["constraints"].passengers,
                ).model_dump(mode="json"),
            )
            rails = result.data or []
            options.extend(rails)
            evidence.update({e.id: e for e in result.evidence})
            context.emit(
                "Rail Search",
                "succeeded" if result.data else "failed",
                "已获得带来源的铁路选项" if result.data else "铁路信息不可用，保留交通缺口",
            )
            if state["constraints"].compare_transport or state["constraints"].transport_mode == "flight":
                flight = await context.registry.call(
                    "Transport",
                    "search_flights",
                    FlightQuery(
                        origin=origin,
                        destination=city,
                        date=state["travel_dates"][day],
                        passengers=state["constraints"].passengers,
                    ).model_dump(mode="json"),
                )
                flights.extend(flight.data or [])
                evidence.update({e.id: e for e in flight.evidence})
                comparisons.append(
                    compare_transport(
                        origin, city, day + 1, rails, flight.data or [], state["constraints"], evidence
                    )
                )
        origin = city
    return {
        "transport_options": options,
        "flight_options": flights,
        "transport_comparisons": comparisons,
        "evidence": evidence,
    }
