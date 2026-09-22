import json
from datetime import datetime, timedelta
from itertools import pairwise

from app.graph.state import AgentState
from app.providers.fixtures import TZ
from app.schemas.travel import Constraints, Issue, Itinerary, ValidationResult
from app.services.context import RunContext
from app.services.costing import reconcile
from app.services.day_planning import preferred


def validate_itinerary(itinerary: Itinerary, constraints: Constraints, state: AgentState) -> ValidationResult:
    result = ValidationResult(valid=True)

    target_context = {}

    def check(
        ok: bool | None,
        kind: str,
        message: str,
        suggestion: str,
        day: int | None = None,
        severity: str = "high",
        observed: str | None = None,
        allowed: str | None = None,
        *,
        target: str | None = None,
        activity_id: str | None = None,
        source: str | None = None,
        evidence: dict | None = None,
        evidence_ids: list[str] | None = None,
    ) -> None:
        result.total_checks += 1
        result.checked_constraints.append(kind)
        if ok is True:
            result.passed_checks += 1
            return
        status = "unverified" if ok is None else "confirmed" if severity == "high" else "informational"
        level = "warning" if status == "unverified" else "error" if status == "confirmed" else "info"
        if ok is None:
            result.unverified_checks.append(f"{kind}:{day or 'trip'}")
        details = {**target_context, **(evidence or {}), "observed": observed, "allowed": allowed}
        result.issues.append(
            Issue(
                type=kind,
                severity=level,
                status=status,
                blocking=status == "confirmed",
                message=message,
                suggestion=suggestion,
                day=day,
                activity_id=(activity_id or None)
                if activity_id is not None
                else target_context.get("activity_id"),
                target=target or target_context.get("target") or (f"day:{day}" if day else "trip"),
                source=source or target_context.get("source", "validator"),
                evidence=details,
                evidence_ids=evidence_ids
                if evidence_ids is not None
                else target_context.get("evidence_ids", []),
                observed=observed,
                allowed=allowed,
            )
        )

    check(len(itinerary.days) == constraints.days, "DAY_COUNT", "行程天数不符合要求。", "保留用户指定天数。")
    visited = {d.city for d in itinerary.days if d.activities}
    check(
        set(constraints.destinations) <= visited,
        "MISSING_DESTINATION",
        "缺少用户要求的城市或当地活动。",
        "为所有目的地安排活动。",
    )
    known_rail = {r.id: r for r in state.get("transport_options", [])}
    route_index = {(r.origin.id, r.destination.id): r for r in state.get("route_data", [])}
    weather = {
        (w.city, w.date): w
        for w in state.get("weather_data", [])
        if (e := state.get("evidence", {}).get(w.evidence_id)) and not e.stale and w.date in e.valid_for
    }
    previous_activity = None
    pending_arrival = None
    for day in itinerary.days:
        d = day.day
        check(
            day.date == constraints.dates[d - 1] if d <= len(constraints.dates) else False,
            "DATE_CONFLICT",
            "行程日期不符合要求。",
            "使用请求中的出行日期。",
            d,
        )
        check(
            bool(day.activities) or day.rail is not None,
            "EMPTY_DAY",
            "当天缺少可用活动。",
            "补充有证据的景点。",
            d,
        )
        check(
            len(day.activities) <= constraints.max_attractions,
            "EXCESSIVE_DENSITY",
            "当天景点数量超出上限。",
            "减少景点数量。",
            d,
            observed=str(len(day.activities)),
            allowed=str(constraints.max_attractions),
        )
        local_minutes = sum(leg.route.duration for leg in day.local_legs)
        check(
            local_minutes <= constraints.max_local_minutes,
            "EXCESSIVE_TRAVEL",
            "当天市内交通耗时过多。",
            "减少跨区域移动。",
            d,
            observed=str(local_minutes),
            allowed=str(constraints.max_local_minutes),
        )
        # Product quality uses the same evidence and existing bounded Critic loop.
        candidates = [p for p in state.get("poi_candidates", []) if p.city == day.city]
        w = weather.get((day.city, day.date))
        full_day = day.origin_city == day.city and not day.rail and not day.flight
        limited = (w is not None and w.severity in {"severe", "adverse"}) or d in constraints.indoor_days
        explicit_rest = any(
            word in state.get("user_query", "") for word in ("休息一天", "只玩一个", "只去一个", "自由活动")
        )
        occupied = sum((a.end - a.start).total_seconds() / 60 for a in day.activities)
        short_window = (
            datetime.combine(day.date, constraints.activity_end, TZ)
            - datetime.combine(day.date, constraints.activity_start, TZ)
        ).total_seconds() / 60 < 300
        if (
            full_day
            and not limited
            and not explicit_rest
            and not short_window
            and constraints.max_attractions >= 2
            and len(candidates) >= 2
        ):
            check(
                len(day.activities) >= 2 or occupied >= 240,
                "DAY_TOO_EMPTY",
                "完整游玩日活动过少。",
                "补充附近且时间允许的景点或夜间活动。",
                d,
                severity="medium",
            )
        check(
            len(day.activities) <= constraints.max_attractions,
            "DAY_TOO_DENSE",
            "每日活动超出所选节奏。",
            "保留重点景点和休息缓冲。",
            d,
        )
        check(
            local_minutes <= constraints.max_local_minutes,
            "EXCESSIVE_TRANSIT",
            "当天交通占用过多时间。",
            "将相邻景点安排在同一天。",
            d,
        )
        if (
            full_day
            and constraints.preferences
            and any(preferred(p, constraints.preferences) for p in candidates)
        ):
            check(
                any(preferred(a.poi, constraints.preferences) for a in day.activities),
                "NO_PREFERENCE_ALIGNMENT",
                "当天未体现已有可行旅行偏好。",
                "选择同区域的历史或夜景活动。",
                d,
                severity="medium",
            )
        if constraints.max_walk_minutes:
            check(
                sum(l.route.duration for l in day.local_legs if l.route.mode == "walk")
                <= constraints.max_walk_minutes,
                "WALK_LIMIT",
                "当天步行时间超出限制。",
                "改用公共交通。",
                d,
            )
        if day.city != day.origin_city:
            check(
                True if day.rail is not None or day.flight is not None else None,
                "TRANSPORT_UNVERIFIED",
                "当前演示数据未覆盖该日期的实时车次，请出行前通过正式票务平台确认。",
                "核对正式票务平台的日期、车次与余票。",
                d,
            )
        if day.rail:
            check(
                day.rail.id in known_rail and day.rail.model_dump() == known_rail[day.rail.id].model_dump(),
                "TRANSPORT_HALLUCINATION",
                "列车信息没有对应的工具证据。",
                "仅使用查询返回的铁路信息。",
                d,
            )
            for leg in day.rail.legs:
                check(
                    leg.availability != "unavailable",
                    "TRANSPORT_UNAVAILABLE",
                    "选中的车次已不可用。",
                    "选择有证据的替代车次。",
                    d,
                )
            first = day.rail.legs[0]
            if previous_activity:
                access = next(
                    (l for l in day.local_legs if l.route.destination.id == first.origin_station.id), None
                )
                check(
                    access.departure >= previous_activity.end
                    and access.arrival + timedelta(minutes=constraints.station_buffer) <= first.departure_time
                    if access
                    else None,
                    "TRANSPORT_CONFLICT" if access else "TRANSPORT_UNVERIFIED",
                    "已知接驳无法满足列车发车与进站缓冲时间。"
                    if access
                    else "尚未获取到达车站的可靠接驳路线。",
                    "提前出发并保留进站缓冲。",
                    d,
                    target=f"station:{first.origin_station.id}",
                    evidence={
                        "departure": first.departure_time.isoformat(),
                        "access_arrival": access.arrival.isoformat() if access else None,
                        "buffer_minutes": constraints.station_buffer,
                    },
                    evidence_ids=[first.evidence_id] + ([access.route.evidence_id] if access else []),
                )
            for a, b in pairwise(day.rail.legs):
                route = route_index.get((a.destination_station.id, b.origin_station.id))
                transfer = (
                    0
                    if a.destination_station.id == b.origin_station.id
                    else (route.duration if route else None)
                )
                impossible = b.departure_time < a.arrival_time + timedelta(
                    minutes=constraints.transfer_buffer + (transfer or 0)
                )
                check(
                    False if impossible else True if transfer is not None else None,
                    "TRANSPORT_CONFLICT" if impossible or transfer is not None else "TRANSPORT_UNVERIFIED",
                    "已知列车换乘时间不足。"
                    if impossible or transfer is not None
                    else "跨站换乘路线尚未验证。",
                    "选择更宽裕的换乘方案。",
                    d,
                    target=f"transfer:{a.train_no}:{b.train_no}",
                    evidence={
                        "arrival": a.arrival_time.isoformat(),
                        "departure": b.departure_time.isoformat(),
                        "transfer_minutes": transfer,
                        "buffer_minutes": constraints.transfer_buffer,
                    },
                    evidence_ids=[a.evidence_id, b.evidence_id],
                )
        if day.flight:
            known = {f.id: f for f in state.get("flight_options", [])}
            check(
                day.flight.id in known and day.flight.model_dump() == known[day.flight.id].model_dump(),
                "FLIGHT_HALLUCINATION",
                "航空方案缺少来源证据。",
                "仅使用查询候选。",
                d,
            )
            check(
                day.flight.availability_status != "unavailable",
                "FLIGHT_UNAVAILABLE",
                "航班不可用。",
                "重新选择候选。",
                d,
            )
        if constraints.transport_mode and day.city != day.origin_city:
            check(
                (bool(day.rail) if constraints.transport_mode == "rail" else bool(day.flight))
                if day.rail or day.flight
                else None,
                "TRANSPORT_MODE" if day.rail or day.flight else "TRANSPORT_UNVERIFIED",
                "交通方式不符合明确要求。",
                "保留硬约束并查询候选。",
                d,
            )
        arrival = (
            day.flight.arrival_time if day.flight else day.rail.legs[-1].arrival_time if day.rail else None
        )
        if constraints.arrival_deadline and arrival:
            check(
                arrival.time() <= constraints.arrival_deadline,
                "ARRIVAL_DEADLINE",
                "交通抵达晚于截止时间。",
                "选择更早候选或报告冲突。",
                d,
            )
        if d in constraints.indoor_days:
            check(
                all(a.poi.environment == "indoor" for a in day.activities),
                "INDOOR_DAY",
                "指定日期仍含户外活动。",
                "选择室内备选。",
                d,
            )
        from types import SimpleNamespace

        arrival_leg = (
            SimpleNamespace(
                destination_station=day.flight.destination_airport, arrival_time=day.flight.arrival_time
            )
            if day.flight
            else day.rail.legs[-1]
            if day.rail
            else pending_arrival
        )
        last = None
        for activity in day.activities:
            poi_evidence = state.get("evidence", {}).get(activity.poi.evidence_id)
            target_context = {
                "activity_id": activity.poi.id,
                "target": activity.poi.id,
                "source": (poi_evidence.source or poi_evidence.provider) if poi_evidence else "poi_tool",
                "evidence_ids": [activity.poi.evidence_id],
            }
            check(
                activity.end > activity.start and (last is None or activity.start >= last.end),
                "TIME_CONFLICT",
                "活动时间发生重叠或顺序错误。",
                "重新安排活动时间。",
                d,
            )
            check(
                activity.start >= datetime.combine(day.date, constraints.activity_start, TZ)
                and activity.end <= datetime.combine(day.date, constraints.activity_end, TZ),
                "ACTIVITY_WINDOW",
                "活动超出用户允许的时间窗口。",
                "调整到允许的时段。",
                d,
            )
            p = activity.poi
            opened = (
                (
                    p.opening_start <= activity.start.time() < p.opening_end
                    and activity.end.time() <= p.opening_end
                )
                if p.opening_start and p.opening_end
                else None
            )
            check(
                opened,
                "OPENING_HOURS_CONFLICT" if opened is not None else "OPENING_HOURS_UNVERIFIED",
                "活动时间超出已知景点开放时间。"
                if opened is not None
                else "暂未获取到该景点的可靠开放时间，建议出行前确认。",
                "调整到已知开放时段。" if opened is not None else "出行前核对景点官方开放时间。",
                d,
                evidence={
                    "opening_start": str(p.opening_start) if p.opening_start else None,
                    "opening_end": str(p.opening_end) if p.opening_end else None,
                    "activity_start": activity.start.isoformat(),
                    "activity_end": activity.end.isoformat(),
                },
            )
            w = weather.get((day.city, day.date))
            weather_ok = (
                None
                if w is None or w.severity == "unknown"
                else None
                if w.severity == "severe" and p.environment == "unknown"
                else not (w.severity == "severe" and p.environment == "outdoor")
            )
            check(
                weather_ok,
                "WEATHER_CONFLICT"
                if weather_ok is not None
                else (
                    "WEATHER_EXPOSURE_UNVERIFIED" if w and w.severity == "severe" else "WEATHER_UNAVAILABLE"
                ),
                "已知严重天气与户外活动存在冲突。"
                if weather_ok is not None
                else (
                    "已有严重天气预报，但景点室内外属性尚未验证。"
                    if w and w.severity == "severe"
                    else "该日期尚无可靠天气预报，请临近出发再次确认。"
                ),
                "改为室内活动。"
                if weather_ok is not None
                else "临近出发再次核对天气；户外暴露未知时也需确认。",
                d,
                target=p.id if weather_ok is False else f"weather:{day.city}:{day.date}",
                activity_id=p.id if weather_ok is False else "",
                source="weather_tool",
                evidence={
                    "city": day.city,
                    "date": day.date.isoformat(),
                    "severity": w.severity if w else None,
                    "environment": p.environment if weather_ok is False else None,
                },
                evidence_ids=[w.evidence_id] if w else [],
            )
            origin = last.poi if last else (arrival_leg.destination_station if arrival_leg else None)
            if origin:
                local = next(
                    (
                        l
                        for l in day.local_legs
                        if l.route.origin.id == origin.id and l.route.destination.id == p.id
                    ),
                    None,
                )
                earliest = last.end if last else arrival_leg.arrival_time
                check(
                    local.departure >= earliest and local.arrival <= activity.start if local else None,
                    "LOCAL_ROUTE_FEASIBILITY" if local else "LOCAL_ROUTE_UNVERIFIED",
                    "已知路线不能满足活动之间预留的交通时间。" if local else "尚未获取活动之间的可靠路线。",
                    "查询实际路线并预留交通时间。",
                    d,
                )
            last = activity
        target_context = {}
        for local in day.local_legs:
            check(
                (local.arrival - local.departure).total_seconds() / 60 >= local.route.duration,
                "LOCAL_DURATION",
                "市内交通所留时长不足。",
                "按路线耗时更新时间。",
                d,
            )
        # Compare at most two provider-supported orders; no straight-line substitution.
        current = [a.poi.id for a in day.activities]
        if len(current) >= 2:

            def length(order: list[str]) -> int | None:
                edges = [route_index.get((a, b)) for a, b in pairwise(order)]
                return sum(r.duration for r in edges) if all(edges) else None

            duration = length(current)
            alternatives = [list(reversed(current)), current[1:] + current[:1]][:2]
            costs = [c for c in (length(o) for o in alternatives) if c is not None]
            if duration is not None and costs:
                check(
                    duration <= min(costs) * 1.3,
                    "ROUTE_INEFFICIENCY",
                    "当前景点顺序存在明显绕路。",
                    "按已验证的较短路线调整顺序。",
                    d,
                    severity="medium",
                )
        inefficient = any(i.type == "ROUTE_INEFFICIENCY" and i.day == d for i in result.issues)
        if inefficient:
            check(
                False,
                "POI_CLUSTER_INEFFICIENT",
                "当天景点存在有路线证据的绕行。",
                "依据已有路线调整顺序或替换邻近景点。",
                d,
                severity="medium",
            )
        previous_activity = day.activities[-1] if day.activities else previous_activity
        pending_arrival = arrival_leg if not day.activities else None
    try:
        recomputed = reconcile(itinerary.model_copy(deep=True), constraints.total_budget)
        check(
            recomputed.model_dump() == itinerary.costs.model_dump(),
            "COST_RECONCILIATION",
            "费用汇总不一致。",
            "重新计算分类与每日费用。",
        )
        check(
            sum(d.estimated_cost for d in itinerary.days) == recomputed.estimated_total,
            "DAILY_COST_TOTAL",
            "每日费用无法核对。",
            "修正费用归属。",
        )
    except ValueError:
        check(False, "DUPLICATE_COST", "同一费用被重复计入。", "每项费用仅记账一次。")
    if constraints.total_budget is not None:
        costs = itinerary.costs
        check(
            costs.known_cost <= constraints.total_budget,
            "BUDGET_EXCEEDED",
            "已知费用下限已超过预算。",
            "调整预算或明确减少付费项目。",
            observed=str(costs.known_cost),
            allowed=str(constraints.total_budget),
            evidence={
                "known_cost": costs.known_cost,
                "estimated_cost": costs.estimated_cost,
                "budget_limit": constraints.total_budget,
            },
        )
        if costs.unknown_cost_items:
            check(
                None,
                "BUDGET_PARTIAL",
                f"当前已知预计费用 ¥{costs.known_cost / 100:,.2f}，部分门票/住宿/实时票价待确认。",
                "出行前确认尚未取得的价格。",
                evidence={"unknown_cost_items": costs.unknown_cost_items},
            )
        if costs.known_cost <= constraints.total_budget < costs.estimated_cost:
            check(
                None,
                "BUDGET_RISK",
                "当前估算费用高于预算，但尚无确定证据证明费用下限超预算。",
                "可按个人选择调整住宿与餐饮估算。",
                evidence={"estimated_cost": costs.estimated_cost},
            )
    if constraints.recommend_hotels:
        from app.providers.amap import straight_distance

        for recommendation in state.get("accommodation", []):
            hotel = next(
                (h for h in recommendation.candidates if h.id == recommendation.selected_hotel_id), None
            )
            if not hotel:
                check(
                    None,
                    "HOTEL_ROUTE_UNVERIFIED",
                    "缺少可用酒店候选及接驳证据。",
                    "出行前确认住宿。",
                    target=f"hotel:{recommendation.city}",
                )
                continue
            target_context = {"target": hotel.id, "source": hotel.source, "evidence_ids": [hotel.evidence_id]}
            pois = [
                a.poi for day in itinerary.days if day.city == recommendation.city for a in day.activities
            ]
            distances = [
                straight_distance(hotel.coordinates, p.coordinates)
                for p in pois
                if hotel.coordinates and p.coordinates
            ]
            check(
                max(distances) <= 15000 if distances else None,
                "HOTEL_TOO_FAR" if distances else "HOTEL_ROUTE_UNVERIFIED",
                "已知住宿地理距离超过15公里阈值。" if distances else "住宿位置与主要景点距离尚未验证。",
                "选择靠近行程景点的住宿。",
                target=f"{hotel.id}:distance",
                evidence={
                    "distance_meters": max(distances) if distances else None,
                    "threshold_meters": 15000,
                },
            )
            check(
                hotel.route.duration <= 60 if hotel.route else None,
                "HOTEL_TOO_FAR" if hotel.route else "HOTEL_ROUTE_UNVERIFIED",
                "已知酒店至主要景点单程通勤超过60分钟。"
                if hotel.route
                else "尚未获取酒店至主要景点的可靠路线。",
                "重新选择住宿区域。" if hotel.route else "出行前核对酒店与景点接驳。",
                target=f"{hotel.id}:poi-route",
                evidence={
                    "route_minutes": hotel.route.duration if hotel.route else None,
                    "threshold_minutes": 60,
                },
            )
            check(
                hotel.station_route.duration <= 75 if hotel.station_route else None,
                "HOTEL_TOO_FAR" if hotel.station_route else "HOTEL_ROUTE_UNVERIFIED",
                "已知酒店至车站通勤超过75分钟。" if hotel.station_route else "尚未获取酒店至车站的可靠路线。",
                "选择车站接驳更方便的住宿。" if hotel.station_route else "出行前核对酒店至车站接驳。",
                target=f"{hotel.id}:station-route",
                evidence={
                    "route_minutes": hotel.station_route.duration if hotel.station_route else None,
                    "threshold_minutes": 75,
                },
            )
    from app.services.validation import finalize_validation

    for mode in ("rail", "flight"):
        evidence = state.get("evidence", {})
        ids = (
            [leg.evidence_id for day in itinerary.days if day.rail for leg in day.rail.legs]
            if mode == "rail"
            else [day.flight.evidence_id for day in itinerary.days if day.flight]
        )
        dataset = any(evidence[eid].source_kind == "dataset" for eid in ids if eid in evidence)
        dataset = dataset or any(
            c.mode == mode and c.provider_mode == "DATASET"
            for comparison in state.get("transport_comparisons", [])
            for c in comparison.candidates
        )
        if dataset:
            result.issues.append(
                Issue(
                    type=f"{mode.upper()}_DATASET",
                    severity="info",
                    status="informational",
                    message=f"{'铁路' if mode == 'rail' else '航班'}为演示数据集，不代表实时余票与库存。",
                    suggestion="出行前通过正式票务平台确认。",
                    source="dataset",
                    target=mode,
                )
            )
    if constraints.recommend_hotels:
        result.issues.append(
            Issue(
                type="HOTEL_AVAILABILITY_INFO",
                severity="info",
                status="informational",
                message="酒店实时价格和房态尚未接入。",
                suggestion="通过正式住宿平台确认。",
                source="hotel_provider",
                target="hotels",
            )
        )
    return finalize_validation(result)


async def critique(state: AgentState, context: RunContext) -> dict:
    context.emit("Critic", "running", "正在校验时间、天气、路线与预算约束")
    draft = state.get("draft_itinerary")
    if draft is None:
        context.emit("Critic", "failed", "没有可校验的行程草案")
        return {"status": "failed", "final_itinerary": None}
    result = validate_itinerary(draft, state["constraints"], state)
    if not any(day.activities for day in draft.days):
        context.emit("Critic", "failed", "缺少可用景点证据，无法生成可用行程")
        return {
            "validation_result": result,
            "status": "failed",
            "final_itinerary": None,
            "stop_reason": "PROVIDER_FAILURE" if not state.get("poi_candidates") else "INVALID_OUTPUT",
        }

    actionable = [i for i in result.issues if i.blocking]
    signature = json.dumps(
        [(i.type, i.day, i.activity_id or i.target, i.observed) for i in actionable], sort_keys=True
    )
    count = state.get("replanning_count", 0)
    replan = (
        bool(actionable)
        and count < context.runtime.policy.max_replanning_attempts
        and signature != state.get("issue_signature")
        and not state.get("stop_reason")
    )
    history = list(state.get("validation_history", [])) + [
        {
            "pass": count,
            "replanning_requested": replan,
            "blocking": [i.model_dump(mode="json") for i in actionable],
            "unverified_count": result.unverified_count,
        }
    ]
    history = history[-(context.runtime.policy.max_replanning_attempts + 1) :]
    if replan:
        hotel_conflicts = any(i.type.startswith("HOTEL_") and i.blocking for i in actionable)
        if hotel_conflicts and state.get("accommodation_reselections", 0) < 1:
            from app.services.accommodation import reselect_for_itinerary

            selected = reselect_for_itinerary(
                state.get("accommodation", []),
                draft,
                state["constraints"].accommodation_preferences,
                once=True,
            )
            context.emit("Critic", "failed", "住宿存在绕路风险，执行一次受控住宿重选")
            return {
                "accommodation": selected,
                "accommodation_reselections": 1,
                "validation_result": result,
                "validation_history": history,
                "replanning_count": count + 1,
                "issue_signature": signature,
                "status": "running",
            }
        context.emit("Critic", "failed", "检测到约束冲突，开始有限次数的调整")
        return {
            "validation_result": result,
            "validation_history": history,
            "replanning_count": count + 1,
            "issue_signature": signature,
            "status": "running",
        }
    status = (
        "conflict"
        if not result.valid
        else ("partial" if result.unverified_count or state.get("stop_reason") else "completed")
    )
    context.emit(
        "Critic",
        "succeeded" if result.valid else "failed",
        "已完成约束校验" if result.valid else "仍有无法满足的约束，已停止自动重规划",
    )
    return {
        "validation_result": result,
        "validation_history": history,
        "status": status,
        "final_itinerary": draft,
    }
