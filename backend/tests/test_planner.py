import pytest
from test_supervisor import context

from app.agents.planner import plan
from app.agents.supervisor import DEMO_QUERY
from app.graph.workflow import build_graph
from app.services.model_client import MockModelClient


async def research_state(c):
    async def identity(state, ctx):
        return {}

    async def end(state, ctx):
        return {"status": "partial"}

    return await build_graph(c, identity, end).ainvoke({"user_query": DEMO_QUERY}, {"recursion_limit": 64})


async def test_planner_actions_observations_and_final():
    c = context(True)
    state = await research_state(c)
    result = await plan(state, c)
    assert len(result["draft_itinerary"].days) == 5
    assert not result["stop_reason"]
    assert c.steps["Travel Planner"] > 1 and c.steps["Travel Planner"] <= 8
    assert any(call["agent"] == "Travel Planner" for call in c.registry.calls)


async def test_duplicate_action_fallback():
    c = context(True)
    state = await research_state(c)
    c.model = MockModelClient(lambda p: {"kind": "action", "tool": "rail_search", "arguments": {}})
    result = await plan(state, c)
    assert result["stop_reason"] == "MAX_STEPS"
    assert c.steps["Travel Planner"] == 8 and result["draft_itinerary"]


async def test_invalid_final_ids_rejected():
    c = context(True)
    state = await research_state(c)
    c.model = MockModelClient(
        lambda p: {"kind": "final", "selections": [{"day": 1, "poi_ids": ["invented"]}]}
    )
    result = await plan(state, c)
    assert result["stop_reason"] == "INVALID_OUTPUT"
    assert all(a.poi.id != "invented" for d in result["draft_itinerary"].days for a in d.activities)


async def test_missing_rail_not_invented():
    c = context(True)
    state = await research_state(c)
    state["transport_options"] = []
    result = await plan(state, c)
    assert all(day.rail is None for day in result["draft_itinerary"].days)


def test_deadline_and_pause_preserve_budget():
    from app.core.budget import ExecutionBudget
    from app.core.errors import ControlledError

    clock = [0.0]
    b = ExecutionBudget(clock=lambda: clock[0], seconds=10)
    clock[0] = 3
    b.pause()
    clock[0] = 100
    b.resume()
    assert b.remaining == 7
    clock[0] = 108
    with pytest.raises(ControlledError):
        b.consume("tool")
