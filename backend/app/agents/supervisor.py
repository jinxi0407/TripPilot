import re
from datetime import date, timedelta

from pydantic import ValidationError

from app.core.errors import ControlledError
from app.graph.state import AgentState
from app.persistence.memory import extract_preferences, normalize_default_window, preference_constraints
from app.providers.fixtures import CITY_CODES
from app.schemas.product import TravelPreferences
from app.schemas.travel import Constraints
from app.services.context import RunContext
from app.services.model_client import MockModelClient, structured_call

DEMO_QUERY = "我想从上海出发，用5天游玩杭州、南京和苏州。预算4000元，喜欢历史景点和夜景，不想每天太赶。请结合高铁、天气、景点位置和市内交通帮我规划行程。"


def parse_fixture(query: str, now: date) -> dict:
    if not query.strip() or len(query) > 4000:
        raise ControlledError("INVALID_INPUT")
    cities = [city for city in CITY_CODES if city in query]
    cities.sort(key=query.index)
    origin_match = re.search(r"(?:从)?(北京|上海|杭州|南京|苏州)(?:出发|去|到)", query)
    origin = origin_match.group(1) if origin_match else (cities[0] if cities else None)
    destinations = [c for c in cities if c != origin] or ([origin] if origin else [])
    nums = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    day_match = re.search(r"(\d+|[一二两三四五六七八九十])(?:天|日游)", query)
    days = (
        int(day_match.group(1))
        if day_match and day_match.group(1).isdigit()
        else nums.get(day_match.group(1))
        if day_match
        else None
    )
    money = re.search(r"(?:预算)?\s*(-?\d+(?:\.\d+)?)\s*元", query)
    dates = re.findall(r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日", query)
    iso = re.findall(r"\d{4}-\d{2}-\d{2}", query)
    try:
        found = [date(int(y or now.year), int(m), int(d)) for y, m, d in dates] or [
            date.fromisoformat(d) for d in iso
        ]
    except ValueError:
        raise ControlledError("INVALID_INPUT") from None
    if "明天" in query:
        found = [now + timedelta(days=1)]
    preferences = [p for p in ["历史", "夜景", "自然"] if p in query]
    return {
        "transport_mode": "flight" if "只坐飞机" in query else "rail" if "只坐高铁" in query else None,
        "origin": origin,
        "destinations": destinations,
        "days": days,
        "start_date": found[0] if found else None,
        "end_date": found[-1] if len(found) > 1 else None,
        "total_budget": round(float(money.group(1)) * 100) if money else None,
        "preferences": preferences,
        "activity_end": "21:30:00" if "夜景" in preferences else "20:00:00",
    }


def distribute_cities(constraints: Constraints) -> list[str]:
    if not constraints.days or not constraints.destinations:
        return []
    quotient, remainder = divmod(constraints.days, len(constraints.destinations))
    return [
        city
        for index, city in enumerate(constraints.destinations)
        for _ in range(quotient + (1 if index < remainder else 0))
    ]


async def supervise(state: AgentState, context: RunContext) -> dict:
    context.emit("Supervisor", "running", "正在理解旅行需求与约束")
    if state.get("replanning_count", 0) > 0:
        context.emit("Supervisor", "succeeded", "已保留原始约束，将校验反馈交给规划器")
        return {"status": "running"}
    existing = state.get("constraints")
    if isinstance(context.model, MockModelClient):
        client = MockModelClient(lambda p: parse_fixture(state["user_query"], context.now.date()))
    else:
        client = context.model
    constraints = await structured_call(
        client,
        {
            "task": "extract_constraints",
            "query": state["user_query"],
            "session_constraints": existing.model_dump(mode="json", exclude_unset=True) if existing else None,
            "travel_preferences": context.memory_preferences,
            "today": context.now.date().isoformat(),
            "instruction": "提取实际指定的约束，未知必填信息留 null。不要推断出行日期。total_budget 单位是人民币分（4000元=400000分）。origin 出发城市不重复加入 destinations。轻松节奏保留默认密度和交通时长限制。",
        },
        Constraints,
        context.budget,
        context.usage,
    )
    data = constraints.model_dump()
    # Preserve explicit facts if structured extraction omitted them. Never infer a departure
    # city merely from a destination mention, and never supply an invented travel date.
    explicit = parse_fixture(state["user_query"], context.now.date())
    for field in ("days", "start_date", "end_date"):
        if not data.get(field) and explicit.get(field):
            data[field] = explicit[field]
    origin_match = re.search(r"从(北京|上海|杭州|南京|苏州)(?:出发|去|到)", state["user_query"])
    if not data.get("origin") and origin_match:
        data["origin"] = origin_match[1]
    if not data.get("destinations") and origin_match:
        data["destinations"] = explicit["destinations"]
    if existing:
        data.update(existing.model_dump(exclude_unset=True))
    if context.memory_preferences:
        data.update(preference_constraints(TravelPreferences.model_validate(context.memory_preferences)))
    # Explicit current preference phrases and API fields override inherited memory.
    if existing:
        data.update(existing.model_dump(exclude_unset=True))
    data.update(
        preference_constraints(TravelPreferences.model_validate(extract_preferences(state["user_query"])))
    )
    data = normalize_default_window(data, existing, state["user_query"])
    if context.demo and not data.get("start_date"):
        data["start_date"] = date(2026, 10, 10)
        data["assumptions"] = data.get("assumptions", []) + ["一键演示采用 2026-10-10 起的合成日期与证据。"]
    if data.get("start_date") and data.get("end_date") and not data.get("days"):
        data["days"] = (data["end_date"] - data["start_date"]).days + 1
    if data.get("start_date") and data.get("days") and not data.get("end_date"):
        data["end_date"] = data["start_date"] + timedelta(days=data["days"] - 1)
    try:
        constraints = Constraints.model_validate(data)
    except ValidationError:
        raise ControlledError("INVALID_INPUT") from None
    missing = [
        label
        for field, label in [
            ("origin", "出发城市"),
            ("destinations", "目的地"),
            ("days", "出行天数"),
            ("start_date", "出发日期"),
        ]
        if not getattr(constraints, field)
    ]
    if missing:
        context.emit("Supervisor", "succeeded", "需要补充出行信息后继续")
        return {
            "constraints": constraints,
            "questions": missing,
            "status": "needs_clarification",
            "routing_plan": [],
            "replanning_count": 0,
        }
    specialists = (
        ["Transport", "Local Travel"]
        if any(c != constraints.origin for c in constraints.destinations)
        else ["Local Travel"]
    )
    context.emit("Supervisor", "succeeded", "约束已提取，已选择所需研究智能体")
    if "Transport" not in specialists:
        context.emit("Rail Search", "skipped", "同城行程，无需查询城际铁路")
    return {
        "constraints": constraints,
        "origin": constraints.origin,
        "destinations": constraints.destinations,
        "travel_dates": constraints.dates,
        "total_budget": constraints.total_budget,
        "preferences": constraints.preferences,
        "city_schedule": distribute_cities(constraints),
        "routing_plan": specialists,
        "questions": [],
        "status": "running",
        "replanning_count": 0,
    }
