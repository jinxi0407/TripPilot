import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from app.core.errors import ControlledError
from app.harness.budget import ExecutionBudget

T = TypeVar("T")
REASONS = {
    "TOOL_DENIED": "TOOL_NOT_ALLOWED",
    "DUPLICATE_ACTION": "DUPLICATE_TOOL_CALL",
    "MAX_STEPS": "STEP_LIMIT_REACHED",
}
TOOL_NAMES = {
    "rail_search": "search_rail",
    "amap_poi": "search_poi",
    "amap_weather": "get_weather",
    "amap_distance": "calculate_distance",
    "amap_route": "plan_route",
}


class RuntimeEvent(BaseModel):
    component: str = Field(max_length=60)
    code: str = Field(max_length=64)
    status: str = Field(max_length=20)
    elapsed_ms: int = Field(ge=0)


class RuntimeHarness:
    def __init__(self, budget: ExecutionBudget):
        self.budget = budget
        self.policy = budget.policy
        self.events: list[RuntimeEvent] = []
        self.failure_reason: str | None = None
        self.on_event: Callable[[RuntimeEvent], None] | None = None
        self.steps: dict[str, int] = {}
        self.fingerprints: dict[str, int] = {}

    def record(self, component: str, code: str, status: str = "failed") -> None:
        code = REASONS.get(code, code)
        if status == "failed":
            self.failure_reason = code
        event = RuntimeEvent(
            component=component,
            code=code,
            status=status,
            elapsed_ms=max(0, round((self.budget.seconds - self.budget.remaining) * 1000)),
        )
        self.events.append(event)
        if self.on_event:
            self.on_event(event)

    def step(self, scope: str) -> None:
        self.budget.check()
        if self.steps.get(scope, 0) >= self.policy.max_react_steps:
            self.record("ReAct", "STEP_LIMIT_REACHED")
            raise ControlledError("MAX_STEPS")
        self.steps[scope] = self.steps.get(scope, 0) + 1

    def permit(self, agent: str, tool: str, allowed: frozenset[str], read_only: bool) -> None:
        if agent not in allowed or not read_only:
            self.record("Harness", "TOOL_NOT_ALLOWED")
            raise ControlledError("TOOL_DENIED")

    def duplicate(self, fingerprint: str, previously_failed: bool = False) -> None:
        count = self.fingerprints.get(fingerprint, 0) + 1
        self.fingerprints[fingerprint] = count
        if previously_failed or count > self.policy.duplicate_call_threshold:
            self.record("Harness", "DUPLICATE_TOOL_CALL")
            raise ControlledError("DUPLICATE_ACTION")

    def consume(self, kind: str) -> None:
        try:
            self.budget.consume(kind)
        except ControlledError as exc:
            reason = {
                "tool": "TOOL_BUDGET_EXCEEDED",
                "external": "EXTERNAL_CALL_BUDGET_EXCEEDED",
                "model": "MODEL_BUDGET_EXCEEDED",
            }.get(kind, exc.error.code)
            self.record("Harness", reason if exc.error.code == "BUDGET_EXHAUSTED" else exc.error.code)
            raise

    def validate(self, schema: Any, value: Any) -> Any:
        try:
            return TypeAdapter(schema).validate_python(value)
        except (ValidationError, ValueError, TypeError):
            self.record("Harness", "INVALID_OUTPUT")
            raise ControlledError("INVALID_OUTPUT") from None

    async def invoke(
        self,
        operation: Callable[[], Awaitable[T]],
        *,
        component: str,
        timeout: float,
        kind: str | None = None,
        external: bool = False,
        retries: int | None = None,
        on_retry: Callable[[], None] | None = None,
    ) -> T:
        limit = self.policy.max_retries if retries is None else min(retries, self.policy.max_retries)
        for attempt in range(limit + 1):
            self.budget.check()
            if kind:
                self.consume(kind)
            if external:
                self.consume("external")
            try:
                async with asyncio.timeout(min(timeout, self.budget.remaining)):
                    result = await operation()
                self.budget.check()
                return result
            except TimeoutError:
                error = ControlledError("TIMEOUT", retryable=True)
            except ControlledError as exc:
                error = exc
            except (ValidationError, ValueError, TypeError, KeyError):
                error = ControlledError("INVALID_OUTPUT")
            except Exception:  # noqa: BLE001 - never expose SDK/provider credentials
                error = ControlledError("PROVIDER_FAILURE")
            self.record(component, error.error.code)
            if (
                attempt == limit
                or not error.error.retryable
                or error.error.code in {"AUTH_REQUIRED", "INVALID_INPUT", "TOOL_DENIED", "TOOL_NOT_ALLOWED"}
            ):
                raise error
            self.record(component, "RETRY", "running")
            if on_retry:
                on_retry()
            await self.budget.backoff()
        raise ControlledError("PROVIDER_FAILURE")

    async def fallback(self, operation: Callable[[], Awaitable[T]], component: str) -> T:
        self.budget.check()
        self.record(component, component.upper() + "_FALLBACK", "running")
        return await operation()

    def snapshot(self) -> dict:
        return {
            "state": "ACTIVE",
            "policy": self.policy.model_dump(),
            "tool_calls": self.budget.tools,
            "external_calls": self.budget.external,
            "model_calls": self.budget.models,
            "elapsed_ms": max(0, round((self.budget.seconds - self.budget.remaining) * 1000)),
            "failure_reason": self.failure_reason,
            "events": [e.model_dump() for e in self.events],
        }
