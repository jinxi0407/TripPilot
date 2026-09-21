import asyncio

import pytest
from pydantic import BaseModel

from app.core.errors import ControlledError
from app.harness.budget import ExecutionBudget
from app.harness.policy import RuntimePolicy
from app.harness.runtime import RuntimeHarness
from app.providers.amap import MockAmapProvider
from app.providers.rail import MockRailProvider
from app.tools.travel import create_registry


def runtime(**overrides):
    policy = RuntimePolicy(**overrides)
    return RuntimeHarness(
        ExecutionBudget(
            policy=policy, max_tools=policy.max_tool_calls, max_external=policy.max_external_calls
        )
    )


def test_step_limit_stops_before_ninth_step():
    rt = runtime(max_react_steps=2)
    rt.step("planner")
    rt.step("planner")
    with pytest.raises(ControlledError):
        rt.step("planner")
    assert rt.steps["planner"] == 2 and rt.failure_reason == "STEP_LIMIT_REACHED"


@pytest.mark.parametrize(
    "kind,code", [("tool", "TOOL_BUDGET_EXCEEDED"), ("external", "EXTERNAL_CALL_BUDGET_EXCEEDED")]
)
async def test_attempt_budgets_include_retries(kind, code):
    rt = runtime(max_tool_calls=1, max_external_calls=1)
    calls = []

    async def fail():
        calls.append(1)
        raise ControlledError("TIMEOUT", retryable=True)

    with pytest.raises(ControlledError):
        await rt.invoke(fail, component="test", kind=kind, timeout=1)
    assert len(calls) == 1 and rt.failure_reason == code


@pytest.mark.parametrize("code", ["AUTH_REQUIRED", "INVALID_INPUT", "TOOL_DENIED"])
async def test_nonrecoverable_never_retried(code):
    rt = runtime(max_retries=3)
    calls = []

    async def fail():
        calls.append(1)
        raise ControlledError(code, retryable=True)

    with pytest.raises(ControlledError):
        await rt.invoke(fail, component="test", timeout=1)
    assert len(calls) == 1


async def test_timeout_cancels_operation_and_retries_bounded():
    rt = runtime()
    cancelled = []

    async def slow():
        try:
            await asyncio.sleep(1)
        finally:
            cancelled.append(True)

    with pytest.raises(ControlledError) as error:
        await rt.invoke(slow, component="MCP", timeout=0.001, external=True)
    assert error.value.error.code == "TIMEOUT"
    assert len(cancelled) == rt.budget.external == 2
    assert any(e.code == "RETRY" for e in rt.events)


async def test_transient_retry_recovers_and_trace_is_safe():
    rt = runtime()
    attempts = []

    async def once():
        attempts.append(1)
        if len(attempts) == 1:
            raise ControlledError("PROVIDER_FAILURE", retryable=True)
        return 42

    assert await rt.invoke(once, component="MCP", timeout=1, external=True) == 42
    assert rt.budget.external == 2 and rt.snapshot()["elapsed_ms"] >= 0


async def test_whitelist_and_duplicate_guard_execute_no_extra_handler():
    registry = create_registry(MockRailProvider(), MockAmapProvider(), ExecutionBudget())
    denied = await registry.call("Travel Planner", "delete_database", {})
    assert denied.error.code == "TOOL_DENIED"
    assert registry.runtime.failure_reason == "TOOL_NOT_ALLOWED"
    for _ in range(2):
        assert (await registry.call("Travel Planner", "search_poi", {"city": "杭州"})).status == "ok"
    repeated = await registry.call("Travel Planner", "search_poi", {"city": "杭州"})
    assert repeated.error.code == "DUPLICATE_ACTION"
    assert registry.budget.tools == 1 and registry.runtime.failure_reason == "DUPLICATE_TOOL_CALL"
    registry.evidence_revision += 1
    assert (await registry.call("Travel Planner", "search_poi", {"city": "杭州"})).status == "ok"


async def test_invalid_schema_not_retried_and_fallback_explicit():
    rt = runtime()

    class Result(BaseModel):
        number: int

    calls = []

    async def invalid():
        calls.append(1)
        return rt.validate(Result, {"number": "not-number"})

    with pytest.raises(ControlledError):
        await rt.invoke(invalid, component="A2A", timeout=1)
    assert len(calls) == 1 and rt.failure_reason == "INVALID_OUTPUT"

    async def local():
        return "local-result"

    assert await rt.fallback(local, "A2A") == "local-result"
    assert rt.events[-1].code == "A2A_FALLBACK"


def test_delegation_reserve_settle_and_unknown_completion():
    budget = ExecutionBudget(max_tools=5, max_external=8)
    lease = budget.reserve(4, 6)
    assert (budget.tools, budget.external) == (4, 6)
    budget.settle(lease, 2, 3)
    assert (budget.tools, budget.external) == (2, 3)
    budget.reserve(3, 5)  # No response: no refund.
    with pytest.raises(ControlledError):
        budget.consume("tool")
    with pytest.raises(ControlledError):
        budget.consume("external")
    with pytest.raises(ControlledError):
        budget.settle((1, 1), 2, 0)


async def test_fallback_cannot_reset_expired_deadline():
    now = [0.0]
    rt = RuntimeHarness(ExecutionBudget(clock=lambda: now[0], seconds=1))
    now[0] = 2

    async def forbidden():
        pytest.fail("expired fallback executed")

    with pytest.raises(ControlledError):
        await rt.fallback(forbidden, "MCP")


def test_explicit_fixture_keeps_v02_local_behavior_when_services_enabled():
    from app.core.config import Settings
    from app.services.engine import create_context
    context = create_context(Settings(protocols_enabled=True), mode="fixture", scenario="outage")
    assert context.protocols is None
    assert context.local_provider.outage


def test_runtime_policy_environment_controls_actual_budget(monkeypatch):
    from app.core.config import Settings
    from app.services.engine import create_context
    monkeypatch.setenv("RUNTIME_POLICY__MAX_TOOL_CALLS", "3")
    context = create_context(Settings(), mode="fixture")
    assert context.runtime.policy.max_tool_calls == context.budget.max_tools == 3
