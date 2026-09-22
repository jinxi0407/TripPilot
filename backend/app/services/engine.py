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
from app.providers.flight import RealFlightProvider
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
    provider_mode: str | None = None,
) -> RunContext:
    policy = settings.runtime_policy
    budget = ExecutionBudget(
        seconds=policy.total_timeout_seconds,
        max_tools=policy.max_tool_calls,
        max_models=policy.max_model_calls,
        max_external=policy.max_external_calls,
        policy=policy,
    )
    model = get_model(settings, mode)
    rail = {"mock": MockRailProvider, "dataset": DatasetRailProvider, "real": RealRailProvider}[
        settings.rail_provider or "mock"
    ]()
    if isinstance(rail, MockRailProvider):
        rail.disruption = scenario == "transport"
    source_mode = provider_mode or ("fixture" if mode == "fixture" else "live")
    use_live = source_mode == "live" and settings.amap_ready
    local = (
        AmapProvider(settings.amap_api_key.get_secret_value(), timeout=policy.tool_timeout_seconds)
        if use_live
        else MockAmapProvider(severe_rain=scenario == "rain", outage=scenario == "outage")
    )
    context = RunContext(
        model,
        create_registry(
            rail, local, budget, flight=RealFlightProvider() if settings.flight_provider == "real" else None
        ),
        budget,
        settings=settings,
        source_mode=source_mode,
        demo=demo,
        local_provider=local,
        rail_mode=settings.rail_provider or "mock",
        simulated_rain=scenario == "rain",
        now=now or (FIXED_NOW if model.name == "fixture" else datetime.now(TZ)),
    )

    if settings.protocols_enabled and (mode != "fixture" or settings.protocol_fixture):
        from app.services.protocols import ProtocolRuntime

        context.protocols = ProtocolRuntime(context, source_mode)
    return context


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
