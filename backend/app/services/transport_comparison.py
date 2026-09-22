from app.schemas.product import TransportCandidate, TransportComparison, TravelTimeEstimate


def time_estimate(duration, mode, buffer=None, access=None, arrival=None):
    """City-centre scenario estimates, not asserted provider travel times."""
    access = access if access is not None else (30 if mode == "rail" else 60)
    arrival = arrival if arrival is not None else (30 if mode == "rail" else 60)
    buffer = buffer if buffer is not None else (45 if mode == "rail" else 120)
    return TravelTimeEstimate(
        local_access_minutes=access,
        recommended_buffer_minutes=buffer,
        scheduled_duration_minutes=duration,
        arrival_transfer_minutes=arrival,
        estimated_total_minutes=access + buffer + duration + arrival,
        access_source="estimated",
        assumptions=["市中心出发/抵达的通用估计；未提供住址，需按真实地址核对接驳。"],
    )


def compare_transport(origin, destination, day, rails, flights, constraints, evidence):
    candidates = []
    for rail in rails:
        if any(l.availability == "unavailable" for l in rail.legs):
            continue
        first, last = rail.legs[0], rail.legs[-1]
        duration = round((last.arrival_time - first.departure_time).total_seconds() / 60)
        if any(
            (b.departure_time - a.arrival_time).total_seconds() / 60 < constraints.transfer_buffer
            for a, b in zip(rail.legs, rail.legs[1:])
        ):
            continue
        prices = [l.price for l in rail.legs]
        e = evidence.get(first.evidence_id)
        candidates.append(
            TransportCandidate(
                id=rail.id,
                mode="rail",
                provider_mode=e.source_kind.upper() if e else "DATASET",
                source=e.source or e.provider if e else "unknown",
                cost=sum(prices) * constraints.passengers if all(x is not None for x in prices) else None,
                transfers=len(rail.legs) - 1,
                departure=first.departure_time.isoformat(),
                arrival=last.arrival_time.isoformat(),
                estimate=time_estimate(duration, "rail", constraints.station_buffer),
                score=0,
                reasons=["铁路接驳/缓冲已纳入门到门估计"],
            )
        )
    for f in flights:
        if f.availability_status == "unavailable":
            continue
        candidates.append(
            TransportCandidate(
                id=f.id,
                mode="flight",
                provider_mode=f.provider_mode,
                source=f.source,
                cost=f.price * constraints.passengers if f.price is not None else None,
                transfers=0,
                departure=f.departure_time.isoformat(),
                arrival=f.arrival_time.isoformat(),
                estimate=time_estimate(f.duration_minutes, "flight"),
                score=0,
                reasons=["机场两端接驳与120分钟候机缓冲已纳入估计"],
            )
        )
    from datetime import datetime

    for c in candidates:
        c.score = float(c.estimate.estimated_total_minutes) + (c.cost / 1000 if c.cost is not None else 100)
        if (constraints.transport_preference == "high_speed_rail" and c.mode == "rail") or (
            constraints.transport_preference == "flight" and c.mode == "flight"
        ):
            c.score -= 25
            c.reasons.append("符合交通偏好，偏好仅用于排序")
        if constraints.avoid_early_departure and datetime.fromisoformat(c.departure).hour < 9:
            c.score += 120
            c.reasons.append("早班需要较早出门，按偏好降低排序")
    eligible = [
        c for c in candidates if not constraints.transport_mode or c.mode == constraints.transport_mode
    ]
    if constraints.arrival_deadline:
        eligible = [
            c for c in eligible if datetime.fromisoformat(c.arrival).time() <= constraints.arrival_deadline
        ]
    selected = min(eligible, key=lambda c: c.score) if eligible else None
    return TransportComparison(
        origin=origin,
        destination=destination,
        day=day,
        candidates=sorted(candidates, key=lambda c: c.score),
        recommended_id=selected.id if selected else None,
        recommendation=(
            "推荐候选："
            + ("高铁" if selected.mode == "rail" else "航班")
            + "；综合门到门估计、费用与偏好排序，接驳仍需核对。"
            if selected
            else "当前证据没有满足交通条件的候选，不能确认可行性。"
        ),
    )
