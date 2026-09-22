"""Small evidence-based selection helpers; no new agent or external provider."""

from itertools import pairwise, permutations

from app.providers.amap import straight_distance


def night_place(poi) -> bool:
    return "夜景" in poi.tags or any(
        s in poi.name for s in ("河坊街", "老门东", "平江路", "秦淮", "外滩", "前门大街")
    )


def preferred(poi, preferences) -> bool:
    return (
        bool(set(poi.tags) & set(preferences))
        or ("夜景" in preferences and night_place(poi))
        or (
            "历史" in preferences
            and any(s in poi.name for s in ("博物", "庙", "贡院", "园", "门东", "河坊街"))
        )
    )


def cluster_order(pois, routes):
    """Use complete Amap route evidence if available, geographic proximity only for shortlist ordering."""
    if len(pois) < 2:
        return pois
    lookup = {(r.origin.id, r.destination.id): r.duration for r in routes}
    options = []
    for order in permutations(pois[:5]):
        if any(night_place(p) for p in order[:-1]):
            continue
        legs = [lookup.get((a.id, b.id)) for a, b in pairwise(order)]
        if all(v is not None for v in legs):
            options.append((sum(legs), order))
    if options:
        return list(min(options, key=lambda item: item[0])[1])
    remaining = list(pois)
    ordered = [remaining.pop(0)]
    while remaining:

        def distance(p):
            a, b = ordered[-1].coordinates, p.coordinates
            return (night_place(p), straight_distance(a, b) if a and b else 100000)

        chosen = min(remaining, key=distance)
        ordered.append(chosen)
        remaining.remove(chosen)
    return ordered


def city_day_pois(candidates, constraints, offset, *, indoor=False, routes=()):
    """2 relaxed / 3 balanced / 4 compact candidates; assembly trims to real feasibility."""
    cap = min(
        constraints.max_attractions, {"relaxed": 2, "balanced": 3, "compact": 4}[constraints.travel_pace]
    )
    if indoor:
        return cluster_order([p for p in candidates if p.environment == "indoor"][:cap], routes)
    daytime = [p for p in candidates if not night_place(p)]
    nights = [p for p in candidates if night_place(p)]
    if "夜景" in constraints.preferences and nights and offset == 0:
        selected = daytime[: max(0, cap - 1)] + nights[:1]
    else:
        consumed = max(0, cap - 1) if nights and "夜景" in constraints.preferences else cap
        fresh = daytime[consumed:] if offset else daytime
        selected = fresh[:cap]
        if len(selected) < min(2, cap):
            selected += [p for p in candidates if p not in selected][: cap - len(selected)]
    return cluster_order(selected[:cap], routes)


def route_mode(a, b, constraints):
    # Geographic distance chooses which Amap route to request; it is never a journey-time estimate.
    if (
        a.coordinates
        and b.coordinates
        and constraints.walking_tolerance != "low"
        and straight_distance(a.coordinates, b.coordinates) <= 1800
    ):
        return "walk"
    return "transit"
