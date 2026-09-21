import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from app.core.budget import ExecutionBudget
from app.core.errors import ControlledError
from app.harness.runtime import TOOL_NAMES, RuntimeHarness
from app.schemas.travel import ToolResult


@dataclass
class Tool:
    name: str
    input_schema: type[BaseModel]
    output_schema: Any
    handler: Callable[[Any], Awaitable[Any]]
    allowed_agents: frozenset[str]
    timeout: float | None = None
    external: bool = False
    read_only: bool = True
    version: str = "1"


class ToolRegistry:
    def __init__(self, tools: list[Tool], budget: ExecutionBudget) -> None:
        self.tools = {t.name: t for t in tools}
        self.budget = budget
        self.runtime = RuntimeHarness(budget)
        self.cache: dict[str, ToolResult] = {}
        self.failed: set[str] = set()
        self.calls: list[dict[str, Any]] = []
        self.evidence_revision = 0
        self.on_event: Callable[[str, str, int], None] | None = None

    def schemas(self, agent: str) -> dict:
        return {
            n: t.input_schema.model_json_schema() for n, t in self.tools.items() if agent in t.allowed_agents
        }

    async def call(self, agent: str, name: str, arguments: dict) -> ToolResult:
        name = {v: k for k, v in TOOL_NAMES.items()}.get(name, name)
        record = {"agent": agent, "tool": name, "status": "requested", "cached": False}
        self.calls.append(record)
        started = self.budget.clock()
        if self.on_event and name in self.tools:
            self.on_event(name, "running", 0)
        try:
            self.budget.check()
            tool = self.tools.get(name)
            self.runtime.permit(agent, name, tool.allowed_agents if tool else frozenset(), bool(tool and tool.read_only))
            try:
                query = tool.input_schema.model_validate(arguments)
            except ValidationError:
                raise ControlledError("INVALID_INPUT") from None
            key = f"{self.evidence_revision}:{name}:" + json.dumps(
                query.model_dump(mode="json"), sort_keys=True
            )
            self.runtime.duplicate(key, key in self.failed)
            if key in self.cache:
                record.update(status="ok", cached=True)
                return self.cache[key].model_copy(deep=True)
            async def attempt():
                raw = await tool.handler(query)
                result = self.runtime.validate(tool.output_schema, raw)
                if result.status == "error" and result.error:
                    raise ControlledError(result.error.code, result.error.retryable)
                return result

            try:
                result = await self.runtime.invoke(
                    attempt, component="Tool", kind="tool", external=tool.external,
                    timeout=tool.timeout or self.runtime.policy.tool_timeout_seconds,
                )
            except ControlledError:
                self.failed.add(key)
                raise
            record["status"] = result.status
            if result.status in ("ok", "empty"):
                self.cache[key] = result
            else:
                self.failed.add(key)
            return result
        except ControlledError as exc:
            record["status"] = exc.error.code
            return ToolResult(status="error", error=exc.error)
        finally:
            record["duration_ms"] = max(0, round((self.budget.clock() - started) * 1000))
            if self.on_event and name in self.tools:
                self.on_event(
                    name,
                    "succeeded" if record["status"] in ("ok", "empty") else "failed",
                    record["duration_ms"],
                )
