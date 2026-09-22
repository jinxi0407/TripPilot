import pytest

from app.agents.critic import validate_itinerary
from app.agents.supervisor import DEMO_QUERY
from app.core.config import Settings
from app.schemas.travel import Constraints
from app.services.costing import reconcile
from app.services.engine import create_context, execute


async def demo(scenario="normal", budget=None):
    c = create_context(Settings(_env_file=None), "fixture", True, scenario)
    state = {"user_query": DEMO_QUERY}
    if budget is not None:
        state["constraints"] = Constraints(total_budget=budget)
    return await execute(state, c), c


async def test_full_demo():
    state, c = await demo()
    assert state["status"] == "completed", state.get("validation_result")
    assert len(state["final_itinerary"].days) == 5
    assert state["validation_result"].valid
    assert state["final_itinerary"].costs.estimated_total <= 400000
    assert c.budget.tools <= 40 and c.steps["Travel Planner"] <= 24


async def test_weather_replan():
    state, _c = await demo("rain")
    assert state["replanning_count"] in (1, 2)
    assert state["status"] == "completed", state["validation_result"]
    assert all(a.poi.environment == "indoor" for d in state["final_itinerary"].days for a in d.activities)


async def test_impossible_budget_stops():
    state, _c = await demo(budget=20000)
    assert state["status"] == "conflict" and state["replanning_count"] <= 2
    assert state["constraints"].total_budget == 20000
    assert any(i.type == "BUDGET_EXCEEDED" for i in state["validation_result"].issues)


async def test_critic_detects_mutated_draft():
    state, _c = await demo()
    draft = state["final_itinerary"].model_copy(deep=True)
    day = draft.days[0]
    day.activities[0].start = day.activities[0].start.replace(hour=23)
    draft.days[-1].activities = []
    result = validate_itinerary(draft, state["constraints"], state)
    types = {i.type for i in result.issues}
    assert {"TIME_CONFLICT", "OPENING_HOURS_CONFLICT", "MISSING_DESTINATION"} <= types


async def test_cost_unknown_and_duplicate():
    state, _c = await demo()
    draft = state["final_itinerary"].model_copy(deep=True)
    draft.days[0].costs[0].amount = None
    draft.costs = reconcile(draft, state["constraints"].total_budget)
    result = validate_itinerary(draft, state["constraints"], state)
    assert "BUDGET_PARTIAL" in {i.type for i in result.issues}
    draft.days[1].costs.append(draft.days[0].costs[0])
    with pytest.raises(ValueError):
        reconcile(draft, 400000)


async def test_graph_limit_and_cancel_are_controlled():
    c = create_context(Settings(_env_file=None), "fixture", True)
    state = await execute({"user_query": DEMO_QUERY}, c, recursion_limit=1)
    assert state["status"] == "failed" and state["stop_reason"] == "GRAPH_LIMIT"
    c = create_context(Settings(_env_file=None), "fixture", True)
    c.budget.cancelled = True
    state = await execute({"user_query": DEMO_QUERY}, c)
    assert state["stop_reason"] == "CANCELLED"
