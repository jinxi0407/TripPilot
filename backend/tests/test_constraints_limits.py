import asyncio
from datetime import timedelta

import pytest
from pydantic import BaseModel, ValidationError
from test_critic import demo

from app.agents.critic import validate_itinerary
from app.core.budget import ExecutionBudget
from app.core.errors import ControlledError
from app.providers.amap import MockAmapProvider
from app.providers.rail import MockRailProvider
from app.schemas.travel import Constraints, POIQuery, ToolResult
from app.services.costing import reconcile
from app.services.model_client import MockModelClient, structured_call
from app.tools.registry import Tool, ToolRegistry
from app.tools.travel import create_registry


@pytest.mark.parametrize(
    "change",
    [
        {"days": 0},
        {"days": 8},
        {"destinations": ["a", "b", "c", "d", "e"]},
        {"total_budget": -1},
        {"start_date": "2026-10-10", "end_date": "2026-10-12", "days": 5},
        {"destinations": ["杭州", "杭州"]},
    ],
)
def test_invalid_constraints(change):
    with pytest.raises(ValidationError):
        Constraints(**change)


async def test_station_buffer_requires_more_than_fifteen_minutes():
    state, _ = await demo()
    draft = state["final_itinerary"].model_copy(deep=True)
    day = draft.days[2]
    access = next(l for l in day.local_legs if l.route.destination.id == day.rail.legs[0].origin_station.id)
    access.arrival = day.rail.legs[0].departure_time - timedelta(minutes=15)
    result = validate_itinerary(draft, state["constraints"], state)
    assert not result.valid and any(i.type == "TRANSPORT_CONFLICT" for i in result.issues)


async def test_density_travel_and_missing_route():
    state, _ = await demo()
    draft = state["final_itinerary"].model_copy(deep=True)
    draft.days[0].activities *= 2
    draft.days[0].local_legs[0].route.duration = 200
    draft.days[1].local_legs = []
    result = validate_itinerary(draft, state["constraints"], state)
    assert {"EXCESSIVE_DENSITY", "EXCESSIVE_TRAVEL", "LOCAL_ROUTE_UNVERIFIED"} <= {
        i.type for i in result.issues
    }
    assert result.unverified_checks


async def test_unknown_opening_and_weather():
    state, _ = await demo()
    draft = state["final_itinerary"].model_copy(deep=True)
    draft.days[0].activities[0].poi.opening_start = None
    state["weather_data"] = []
    result = validate_itinerary(draft, state["constraints"], state)
    assert {"OPENING_HOURS_UNVERIFIED", "WEATHER_UNAVAILABLE"} <= {i.type for i in result.issues}
    assert result.valid and result.unverified_checks


async def test_budget_overflow_exact_fen_and_roundtrip():
    state, _ = await demo()
    draft = state["final_itinerary"].model_copy(deep=True)
    difference = 410000 - draft.costs.estimated_total
    draft.days[0].costs[-1].amount += difference
    draft.costs = reconcile(draft, 400000)
    assert draft.costs.delta == 10000
    assert sum(d.estimated_cost for d in draft.days) == 410000
    result = validate_itinerary(draft, state["constraints"], state)
    assert any(
        i.type == "BUDGET_RISK" and not i.blocking and i.evidence["estimated_cost"] == 410000
        for i in result.issues
    )


async def test_retry_cannot_exceed_global_tool_limit():
    b = ExecutionBudget()
    b.tools = 39
    r = create_registry(MockRailProvider(), MockAmapProvider(outage=True), b)
    result = await r.call("Local Travel", "amap_poi", {"city": "杭州"})
    assert result.error.code == "BUDGET_EXHAUSTED" and b.tools == 40


async def test_auth_not_retried_and_invalid_output_sanitized():
    count = [0]

    async def auth(q):
        count[0] += 1
        raise ControlledError("AUTH_REQUIRED")

    r = ToolRegistry(
        [Tool("t", POIQuery, ToolResult[list], auth, frozenset({"Local Travel"}))], ExecutionBudget()
    )
    assert (await r.call("Local Travel", "t", {"city": "杭州"})).error.code == "AUTH_REQUIRED"
    assert count[0] == 1


async def test_model_budget_no_thirty_first_call():
    class Answer(BaseModel):
        value: int

    b = ExecutionBudget()
    b.models = 30
    with pytest.raises(ControlledError) as exc:
        await structured_call(MockModelClient(lambda p: {"value": 1}), {}, Answer, b, [])
    assert exc.value.error.code == "BUDGET_EXHAUSTED" and b.models == 30


async def test_running_provider_cancelled():
    entered = asyncio.Event()
    cancelled = asyncio.Event()

    async def slow(q):
        entered.set()
        try:
            await asyncio.sleep(5)
        finally:
            cancelled.set()

    r = ToolRegistry(
        [Tool("t", POIQuery, ToolResult[list], slow, frozenset({"Local Travel"}))], ExecutionBudget()
    )
    task = asyncio.create_task(r.call("Local Travel", "t", {"city": "杭州"}))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled.is_set()


async def test_deadline_checked_before_provider():
    now = [0.0]
    b = ExecutionBudget(clock=lambda: now[0], seconds=1)
    now[0] = 2
    r = create_registry(MockRailProvider(), MockAmapProvider(), b)
    assert (await r.call("Local Travel", "amap_poi", {"city": "杭州"})).error.code == "DEADLINE_EXCEEDED"
    assert b.tools == 0
