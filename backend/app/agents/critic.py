import json
from datetime import datetime, timedelta
from itertools import pairwise

from app.graph.state import AgentState
from app.providers.fixtures import TZ
from app.schemas.travel import Constraints, Issue, Itinerary, ValidationResult
from app.services.context import RunContext
from app.services.costing import reconcile


def validate_itinerary(itinerary: Itinerary, constraints: Constraints, state: AgentState) -> ValidationResult:
    result = ValidationResult(valid=True)

    def check(
        ok: bool | None,
        kind: str,
        message: str,
        suggestion: str,
        day: int | None = None,
        severity: str = "high",
        observed: str | None = None,
        allowed: str | None = None,
    ) -> None:
        result.total_checks += 1
        result.checked_constraints.append(kind)
        if ok is True:
            result.passed_checks += 1
        elif ok is None:
            result.unverified_checks.append(f"{kind}:{day or 'trip'}")
            result.issues.append(
                Issue(type=kind, severity="medium", message=message, suggestion=suggestion, day=day)
            )
        else:
            result.issues.append(
                Issue(
                    type=kind,
                    severity=severity,
                    message=message,
                    suggestion=suggestion,
                    day=day,
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
    weather = {(w.city, w.date): w for w in state.get("weather_data", [])}
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
                day.rail is not None,
                "MISSING_TRANSPORT",
                "缺少城际交通证据。",
                "查询有效车次或调整目的地。",
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
                    "TRAIN_DEPARTURE_RISK",
                    "到达车站后预留时间不足或接驳数据缺失。",
                    "提前出发并保留进站缓冲。",
                    d,
                )
            for a, b in pairwise(day.rail.legs):
                route = route_index.get((a.destination_station.id, b.origin_station.id))
                transfer = (
                    0
                    if a.destination_station.id == b.origin_station.id
                    else (route.duration if route else None)
                )
                check(
                    b.departure_time
                    >= a.arrival_time + timedelta(minutes=constraints.transfer_buffer + transfer)
                    if transfer is not None
                    else None,
                    "TRANSFER_RISK",
                    "铁路换乘时间不足或跨站路线未知。",
                    "选择更宽裕的换乘方案。",
                    d,
                )
        arrival_leg = day.rail.legs[-1] if day.rail else pending_arrival
        last = None
        for activity in day.activities:
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
                "OPENING_TIME_CONFLICT" if opened is not None else "OPENING_TIME_UNKNOWN",
                "活动不在开放时间内或开放时间未知。",
                "调整时间或确认官方开放信息。",
                d,
            )
            w = weather.get((day.city, day.date))
            weather_ok = (
                None
                if w is None or w.severity == "unknown"
                else not (w.severity == "severe" and p.environment != "indoor")
            )
            check(
                weather_ok,
                "WEATHER_RISK" if weather_ok is not None else "WEATHER_UNKNOWN",
                "天气不适合户外活动或预报暂不可用。",
                "严重天气改为室内活动，缺失预报需临行确认。",
                d,
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
                    "LOCAL_ROUTE_FEASIBILITY",
                    "活动之间交通时间不足或路线缺失。",
                    "查询实际路线并预留交通时间。",
                    d,
                )
            last = activity
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
        check(
            itinerary.costs.estimated_total <= constraints.total_budget,
            "BUDGET_EXCEEDED",
            "预计总费用超过预算。",
            "选择低价活动、住宿预算或由用户调整预算。",
            observed=str(itinerary.costs.estimated_total),
            allowed=str(constraints.total_budget),
        )
        if itinerary.costs.unknown_items:
            check(None, "BUDGET_UNKNOWN", "部分费用未知，不能确认预算合规。", "确认缺失票价与费用。")
    result.valid = not any(i.severity == "high" for i in result.issues)
    return result


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

    actionable = [i for i in result.issues if i.severity == "high" or i.type == "ROUTE_INEFFICIENCY"]
    signature = json.dumps([(i.type, i.day, i.observed) for i in actionable], sort_keys=True)
    count = state.get("replanning_count", 0)
    replan = (
        bool(actionable)
        and count < context.runtime.policy.max_replanning_attempts
        and signature != state.get("issue_signature")
        and not state.get("stop_reason")
    )
    if replan:
        context.emit("Critic", "failed", "检测到约束冲突，开始有限次数的调整")
        return {
            "validation_result": result,
            "replanning_count": count + 1,
            "issue_signature": signature,
            "status": "running",
        }
    status = (
        "conflict"
        if not result.valid
        else ("partial" if result.unverified_checks or state.get("stop_reason") else "completed")
    )
    context.emit(
        "Critic",
        "succeeded" if result.valid else "failed",
        "已完成约束校验" if result.valid else "仍有无法满足的约束，已停止自动重规划",
    )
    return {"validation_result": result, "status": status, "final_itinerary": draft}
