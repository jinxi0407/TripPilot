from app.graph.state import AgentState
from app.schemas.travel import RailQuery
from app.services.context import RunContext


async def research_transport(state: AgentState, context: RunContext) -> dict:
    options, evidence = [], dict(state.get("evidence", {}))
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
            options.extend(result.data or [])
            evidence.update({e.id: e for e in result.evidence})
            context.emit(
                "Rail Search",
                "succeeded" if result.data else "failed",
                "已获得带来源的铁路选项" if result.data else "铁路信息不可用，保留交通缺口",
            )
        origin = city
    return {"transport_options": options, "evidence": evidence}
