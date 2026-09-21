from app.graph.state import AgentState
from app.providers.fixtures import STATIONS
from app.schemas.travel import Evidence, Place, POIQuery, RouteQuery, WeatherQuery, WeatherRecord
from app.services.context import RunContext


async def research_local(state: AgentState, context: RunContext) -> dict:
    pois, weather, routes = [], [], []
    evidence = dict(state.get("evidence", {}))
    for city in dict.fromkeys(state["city_schedule"]):
        context.emit("Amap POI", "running", f"正在搜索{city}的历史景点与室内备选")
        result = await context.registry.call("Local Travel", "amap_poi", POIQuery(city=city).model_dump())
        items = result.data or []
        if context.model.name == "qwen" and getattr(context.local_provider, "status", None) == "LIVE":
            # Search explicitly named landmarks, avoiding arbitrary nearby schools or duplicate sub-POIs.
            landmarks = {
                "杭州": ("西湖", "浙江自然博物院"),
                "南京": ("夫子庙", "南京博物院"),
                "苏州": ("拙政园", "苏州博物馆"),
                "上海": ("外滩", "上海博物馆"),
            }
            names = landmarks.get(city)
            if names:
                items = []
                for name in names:
                    search = await context.registry.call(
                        "Local Travel", "amap_poi", POIQuery(city=city, keywords=name, limit=3).model_dump()
                    )
                    if search.data:
                        items.append(search.data[0])
                    evidence.update({e.id: e for e in search.evidence})
        pois.extend(items)
        evidence.update({e.id: e for e in result.evidence})
        context.emit(
            "Amap POI",
            "succeeded" if items else "failed",
            "已收集景点候选及来源" if items else "景点服务不可用，已记录数据缺口",
        )
        days = [d for d, c in zip(state["travel_dates"], state["city_schedule"]) if c == city]
        result = await context.registry.call(
            "Local Travel", "amap_weather", WeatherQuery(city=city, dates=days).model_dump(mode="json")
        )
        weather.extend(result.data or [])
        evidence.update({e.id: e for e in result.evidence})
        if context.simulated_rain and context.model.name == "qwen":
            eid = f"simulated-rain-{city}"
            evidence[eid] = Evidence(
                id=eid,
                provider="UserWeatherSimulation",
                source_kind="mock",
                source="weather_simulation",
                retrieved_at=context.now,
                valid_for=days,
                notes="用户主动模拟暴雨；不是高德真实天气预报。",
            )
            weather = [w for w in weather if w.city != city]
            weather.extend(
                WeatherRecord(
                    city=city, date=d, condition="暴雨（用户模拟）", severity="severe", evidence_id=eid
                )
                for d in days
            )
        # A small route shortlist: station access, two daytime POIs, indoor alternative and night view.
        selected = items[:4]
        station = STATIONS.get(city)
        pairs = []
        if station and selected:
            pairs.extend([(station, selected[1])] if len(selected) > 1 else [])
            pairs.append((selected[2] if len(selected) > 2 else selected[-1], station))
        if len(selected) > 1:
            pairs.append((selected[0], selected[1]))
        if len(selected) > 2:
            pairs.append((selected[1], selected[2]))
        if len(selected) > 3:
            pairs.extend([(selected[1], selected[3]), (selected[3], selected[2])])
        if getattr(context.local_provider, "status", None) == "LIVE" and station and selected:
            # Prepare actual station access for conservative one-activity arrival days.
            # Leave the final arrival route to the Planner's Action/Observation loop.
            pairs = [(selected[-1], station)]
            if len(selected) > 1:
                pairs.append((station, selected[1]))
            if city != state["city_schedule"][-1]:
                pairs.append((station, selected[0]))
        for a, b in pairs:
            q = RouteQuery(
                origin=Place.model_validate(a.model_dump(include={"id", "name", "city", "coordinates"})),
                destination=Place.model_validate(b.model_dump(include={"id", "name", "city", "coordinates"})),
            )
            result = await context.registry.call("Local Travel", "amap_route", q.model_dump(mode="json"))
            routes.extend(result.data or [])
            evidence.update({e.id: e for e in result.evidence})
    context.emit("Local Travel", "succeeded", "本地景点、天气与交通研究已汇总")
    return {"poi_candidates": pois, "weather_data": weather, "route_data": routes, "evidence": evidence}
