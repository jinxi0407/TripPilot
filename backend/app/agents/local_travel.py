from itertools import pairwise

from app.graph.state import AgentState
from app.providers.amap import AmapProvider
from app.providers.fixtures import STATIONS
from app.schemas.travel import Evidence, Place, POIQuery, RouteQuery, WeatherQuery, WeatherRecord
from app.services.context import RunContext
from app.services.day_planning import city_day_pois, route_mode


async def research_local(state: AgentState, context: RunContext) -> dict:
    pois, weather, routes = [], [], []
    evidence = dict(state.get("evidence", {}))
    for city in dict.fromkeys(state["city_schedule"]):
        context.emit("Amap POI", "running", f"正在搜索{city}的历史景点与室内备选")
        live = context.source_mode == "live" and isinstance(context.local_provider, AmapProvider)
        landmarks = {
            "杭州": ("西湖", "浙江省博物馆(孤山馆区)", "中国丝绸博物馆", "河坊街"),
            "南京": ("夫子庙", "江南贡院", "南京博物院", "老门东"),
            "苏州": ("拙政园", "苏州博物馆", "平江路"),
            "上海": ("上海博物馆", "上海市历史博物馆", "外滩"),
            "北京": ("故宫博物院", "中国国家博物馆", "前门大街"),
        }
        items = []
        for name in landmarks.get(city, ("",)) if live else ("",):
            result = await context.registry.call(
                "Local Travel",
                "amap_poi",
                POIQuery(city=city, keywords=name, limit=3 if live else 12).model_dump(),
            )
            if result.data:
                items.extend(result.data[:1] if live else result.data)
            evidence.update({e.id: e for e in result.evidence})
        items = list({p.id: p for p in items}.values())
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
        if live and station and items:
            pairs = []
            city_indices = [i for i, c in enumerate(state["city_schedule"]) if c == city]
            for offset, index in enumerate(city_indices):
                indoor = context.simulated_rain or index + 1 in state["constraints"].indoor_days
                chosen = city_day_pois(items, state["constraints"], offset, indoor=indoor)
                if chosen:
                    if offset == 0 and city != state["constraints"].origin:
                        pairs.append((station, chosen[0]))
                    pairs.extend(pairwise(chosen))
                    if index + 1 < len(state["city_schedule"]) and state["city_schedule"][index + 1] != city:
                        pairs.append((chosen[-1], station))
            pairs = list({(a.id, b.id): (a, b) for a, b in pairs}.values())
        for a, b in pairs:
            q = RouteQuery(
                origin=Place.model_validate(a.model_dump(include={"id", "name", "city", "coordinates"})),
                destination=Place.model_validate(b.model_dump(include={"id", "name", "city", "coordinates"})),
                mode=route_mode(a, b, state["constraints"]) if live else "transit",
            )
            result = await context.registry.call("Local Travel", "amap_route", q.model_dump(mode="json"))
            routes.extend(result.data or [])
            evidence.update({e.id: e for e in result.evidence})
    context.emit("Local Travel", "succeeded", "本地景点、天气与交通研究已汇总")
    accommodation = []
    if state["constraints"].recommend_hotels:
        from app.services.accommodation import research_accommodation

        accommodation, evidence = await research_accommodation(
            {**state, "poi_candidates": pois, "evidence": evidence}, context
        )
    return {
        "poi_candidates": pois,
        "weather_data": weather,
        "route_data": routes,
        "accommodation": accommodation,
        "evidence": evidence,
    }
