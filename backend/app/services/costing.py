from app.schemas.travel import CostSummary, Itinerary

CATEGORIES = ["inter_city", "local_transport", "accommodation", "tickets", "food", "reserve"]


def reconcile(itinerary: Itinerary, budget: int | None) -> CostSummary:
    totals = dict.fromkeys(CATEGORIES, 0)
    unknown, seen = [], set()
    for day in itinerary.days:
        day_total = 0
        for item in day.costs:
            if item.id in seen:
                raise ValueError("duplicate expense")
            seen.add(item.id)
            if item.amount is None:
                unknown.append(item.id)
            else:
                totals[item.category] += item.amount
                day_total += item.amount
        day.estimated_cost = day_total
    total = sum(totals.values())
    return CostSummary(
        categories=totals,
        estimated_total=total,
        unknown_items=unknown,
        budget=budget,
        delta=total - budget if budget is not None else None,
    )
