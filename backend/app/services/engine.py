import asyncio
from datetime import datetime

from langgraph.errors import GraphRecursionError

from app.agents.critic import critique
from app.agents.planner import plan
from app.core.budget import ExecutionBudget
from app.core.config import Settings
from app.core.errors import ControlledError
from app.graph.state import AgentState
from app.graph.workflow import build_graph
from app.providers.amap import AmapProvider, MockAmapProvider
from app.providers.fixtures import FIXED_NOW, TZ
from app.providers.rail import DatasetRailProvider, MockRailProvider, RealRailProvider
from app.services.context import RunContext
from app.services.model_client import get_model
from app.tools.travel import create_registry


def create_context(
    settings: Settings,
    mode: str = "auto",
    demo: bool = False,
    scenario: str = "normal",
    now: datetime | None = None,
) -> RunContext:
    budget = ExecutionBudget()
    model = get_model(settings, mode)
    rail = {"mock": MockRailProvider, "dataset": DatasetRailProvider, "real": RealRailProvider}[
        settings.rail_provider or "mock"
    ]()
    if isinstance(rail, MockRailProvider):
        rail.disruption = scenario == "transport"
    use_live = mode != "fixture" and settings.amap_ready
    local = (
        AmapProvider(settings.amap_api_key.get_secret_value())
        if use_live
        else MockAmapProvider(severe_rain=scenario == "rain", outage=scenario == "outage")
    )
    return RunContext(
        model,
        create_registry(rail, local, budget),
        budget,
        demo=demo,
        local_provider=local,
        rail_mode=settings.rail_provider or "mock",
        simulated_rain=scenario == "rain",
        now=now or (FIXED_NOW if model.name == "fixture" else datetime.now(TZ)),
    )


async def execute(state: AgentState, context: RunContext, recursion_limit: int = 64) -> AgentState:
    latest = dict(state)

    async def capture_planner(current, ctx):
        result = await plan(current, ctx)
        latest.update(current)
        latest.update(result)
        return result

    try:
        async with asyncio.timeout(context.budget.remaining):
            return await build_graph(context, capture_planner, critique).ainvoke(
                state, {"recursion_limit": recursion_limit}
            )
    except asyncio.CancelledError:
        context.budget.cancelled = True
        context.emit("System", "failed", "任务已取消")
        return {**latest, "status": "cancelled", "agent_trace": list(context.trace)}
    except (ControlledError, TimeoutError, GraphRecursionError) as exc:
        code = (
            exc.error.code
            if isinstance(exc, ControlledError)
            else ("GRAPH_LIMIT" if isinstance(exc, GraphRecursionError) else "DEADLINE_EXCEEDED")
        )
        context.emit("System", "failed", ControlledError(code).error.message)
        latest.update(stop_reason=code, status="cancelled" if code == "CANCELLED" else "failed")
        if latest.get("draft_itinerary"):
            result = await critique(latest, context)
            latest.update(result)
        return {**latest, "agent_trace": list(context.trace)}
