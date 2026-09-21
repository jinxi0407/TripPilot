from datetime import date

import pytest

from app.agents.supervisor import DEMO_QUERY, parse_fixture, supervise
from app.core.budget import ExecutionBudget
from app.core.errors import ControlledError
from app.graph.workflow import build_graph
from app.providers.amap import MockAmapProvider
from app.providers.rail import MockRailProvider
from app.services.context import RunContext
from app.services.model_client import MockModelClient
from app.tools.travel import create_registry


def context(demo=False):
    budget = ExecutionBudget()
    return RunContext(
        MockModelClient(), create_registry(MockRailProvider(), MockAmapProvider(), budget), budget, demo=demo
    )


async def test_representative_clarifies_dates():
    c = context()
    state = await supervise({"user_query": DEMO_QUERY}, c)
    assert state["status"] == "needs_clarification"
    assert state["constraints"].total_budget == 400000
    assert state["constraints"].destinations == ["杭州", "南京", "苏州"]
    assert c.budget.tools == 0


async def test_fixture_demo_and_local_routing():
    state = await supervise({"user_query": DEMO_QUERY}, context(True))
    assert len(state["city_schedule"]) == 5 and state["routing_plan"] == ["Transport", "Local Travel"]
    state = await supervise({"user_query": "10月10日在杭州玩1天，预算500元。"}, context())
    assert state["routing_plan"] == ["Local Travel"]


async def test_graph_research_state_and_no_rail_for_local():
    c = context()

    async def planner(state, ctx):
        assert state["poi_candidates"] and state["weather_data"] and state["route_data"]
        return {"draft_itinerary": None}

    async def critic(state, ctx):
        return {"status": "partial"}

    result = await build_graph(c, planner, critic).ainvoke(
        {"user_query": "10月10日在杭州玩1天，预算500元。"}, {"recursion_limit": 64}
    )
    assert result["status"] == "partial" and result["evidence"]
    assert not any(call["tool"] == "rail_search" for call in c.registry.calls)


def test_relative_dates_and_invalid_date():
    assert parse_fixture("明天从上海去杭州玩2天", date(2026, 10, 9))["start_date"] == date(2026, 10, 10)
    with pytest.raises(ControlledError):
        parse_fixture("13月45日杭州1日游", date(2026, 10, 1))


async def test_negative_budget_rejected():
    with pytest.raises(ControlledError):
        await supervise({"user_query": "10月10日杭州1日游，预算-10元"}, context())
