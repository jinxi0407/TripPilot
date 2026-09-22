from app.providers.amap import straight_distance
from app.providers.fixtures import STATIONS
from app.schemas.product import AccommodationRecommendation, HotelQuery
from app.schemas.travel import Coordinates, DistanceQuery, Place, RouteQuery


def center_of(pois):
    points = [p.coordinates for p in pois if p.coordinates]
    if not points:
        return None
    return Coordinates(
        longitude=sum(p.longitude for p in points) / len(points),
        latitude=sum(p.latitude for p in points) / len(points),
    )


def hotel_score(hotel, pois, station=None, preferences=()):
    if not hotel.coordinates:
        return float("inf")
    distances = [straight_distance(hotel.coordinates, p.coordinates) for p in pois if p.coordinates]
    score = sum(distances) / len(distances) if distances else 100000
    if station and station.coordinates:
        score += straight_distance(hotel.coordinates, station.coordinates) * (
            0.3 if "near_station" in preferences else 0.1
        )
    if "near_metro" in preferences and hotel.metro_access == "verified":
        score -= 300
    return score


def reselect_for_itinerary(recommendations, itinerary, preferences, once=False):
    result = []
    for recommendation in recommendations:
        r = recommendation.model_copy(deep=True)
        pois = [a.poi for day in itinerary.days if day.city == r.city for a in day.activities]
        r.main_poi_ids = list(dict.fromkeys(p.id for p in pois))
        names = list(dict.fromkeys(p.name for p in pois))
        r.recommended_area = " / ".join(names[:2]) + "周边活动区域" if names else r.recommended_area
        ranked = sorted(r.candidates, key=lambda h: hotel_score(h, pois, STATIONS.get(r.city), preferences))
        if ranked:
            selected = (
                next((h for h in ranked if h.id == r.selected_hotel_id), ranked[0])
                if r.reselected and not once
                else ranked[0]
            )
            if once and r.selected_hotel_id == selected.id and len(ranked) > 1:
                selected = ranked[1]
            r.reselected = r.reselected or once
            r.selected_hotel_id = selected.id
            r.candidates = ranked
        result.append(r)
    return result


async def research_accommodation(state, context):
    constraints = state["constraints"]
    recommendations = []
    evidence = dict(state.get("evidence", {}))
    for city in dict.fromkeys(state["city_schedule"]):
        pois = [p for p in state.get("poi_candidates", []) if p.city == city][:4]
        center = center_of(pois)
        result = await context.registry.call(
            "Local Travel", "search_hotels", HotelQuery(city=city, center=center).model_dump(mode="json")
        )
        evidence.update({e.id: e for e in result.evidence})
        candidates = result.data or []
        station = STATIONS.get(city)
        candidates = sorted(
            candidates, key=lambda h: hotel_score(h, pois, station, constraints.accommodation_preferences)
        )
        if candidates and pois and center:
            chosen = candidates[0]
            if chosen.coordinates:
                distance = await context.registry.call(
                    "Local Travel",
                    "calculate_distance",
                    DistanceQuery(origin=chosen.coordinates, destination=center).model_dump(mode="json"),
                )
                evidence.update({e.id: e for e in distance.evidence})
                if distance.data:
                    chosen.distance_meters = distance.data[0].meters
                    chosen.distance_kind = (
                        "provider"
                        if distance.evidence and distance.evidence[0].source_kind == "live"
                        else "estimated_straight"
                    )
                start = Place.model_validate(chosen.model_dump(include={"id", "name", "city", "coordinates"}))
                destinations = [("route", pois[0]), ("station_route", station)]
                for field, dest in destinations:
                    if dest is None:
                        continue
                    q = RouteQuery(
                        origin=start,
                        destination=Place.model_validate(
                            dest.model_dump(include={"id", "name", "city", "coordinates"})
                        ),
                    )
                    route = await context.registry.call(
                        "Local Travel", "plan_route", q.model_dump(mode="json")
                    )
                    evidence.update({e.id: e for e in route.evidence})
                    if route.data:
                        setattr(chosen, field, route.data[0])
        names = " / ".join(p.name for p in pois[:2])
        recommendations.append(
            AccommodationRecommendation(
                city=city,
                days=[i + 1 for i, c in enumerate(state["city_schedule"]) if c == city],
                recommended_area=f"{names}周边活动区域" if names else f"{city}住宿区域待确认",
                reasons=[
                    "按当天景点坐标中心检索，优先减少往返距离。",
                    "综合酒店至主要景点及铁路站点的可用路线。",
                ]
                + (
                    ["偏好靠近地铁；POI不提供已验证的地铁接驳，需另行确认。"]
                    if "near_metro" in constraints.accommodation_preferences
                    else []
                ),
                candidates=candidates,
                selected_hotel_id=candidates[0].id if candidates else None,
                main_poi_ids=[p.id for p in pois],
                station_id=station.id if station else None,
            )
        )
    context.emit("Local Travel", "succeeded", "已按行程区域生成住宿候选；实时房价和房态未接入")
    return recommendations, evidence
