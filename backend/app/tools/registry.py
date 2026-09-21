import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError

from app.core.budget import ExecutionBudget
from app.core.errors import ControlledError
from app.schemas.travel import ToolResult


@dataclass
class Tool:
    name: str
    input_schema: type[BaseModel]
    output_schema: Any
    handler: Callable[[Any], Awaitable[Any]]
    allowed_agents: frozenset[str]
    timeout: float = 10
    read_only: bool = True
    version: str = "1"


class ToolRegistry:
    def __init__(self, tools: list[Tool], budget: ExecutionBudget) -> None:
        self.tools = {t.name: t for t in tools}
        self.budget = budget
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
        record = {"agent": agent, "tool": name, "status": "requested", "cached": False}
        self.calls.append(record)
        started = self.budget.clock()
        if self.on_event and name in self.tools:
            self.on_event(name, "running", 0)
        try:
            self.budget.check()
            tool = self.tools.get(name)
            if tool is None or agent not in tool.allowed_agents or not tool.read_only:
                raise ControlledError("TOOL_DENIED")
            try:
                query = tool.input_schema.model_validate(arguments)
            except ValidationError:
                raise ControlledError("INVALID_INPUT") from None
            key = f"{self.evidence_revision}:{name}:" + json.dumps(
                query.model_dump(mode="json"), sort_keys=True
            )
            if key in self.cache:
                record.update(status="ok", cached=True)
                return self.cache[key].model_copy(deep=True)
            if key in self.failed:
                raise ControlledError("DUPLICATE_ACTION")
            for attempt in range(2):
                self.budget.consume("tool")
                try:
                    async with asyncio.timeout(min(tool.timeout, self.budget.remaining)):
                        raw = await tool.handler(query)
                    self.budget.check()
                    result = TypeAdapter(tool.output_schema).validate_python(raw)
                    if result.status == "error" and result.error:
                        raise ControlledError(result.error.code, result.error.retryable)
                    record["status"] = result.status
                    if result.status in ("ok", "empty"):
                        self.cache[key] = result
                    else:
                        self.failed.add(key)
                    return result
                except TimeoutError:
                    error = ControlledError("TIMEOUT", retryable=True)
                except (ValidationError, ValueError, TypeError, KeyError):
                    error = ControlledError("INVALID_OUTPUT")
                except ControlledError as exc:
                    error = exc
                except Exception:  # noqa: BLE001 - external provider boundary; never expose raw errors
                    error = ControlledError("PROVIDER_FAILURE")
                if attempt or not error.error.retryable:
                    self.failed.add(key)
                    raise error
                await self.budget.backoff()
            raise ControlledError("PROVIDER_FAILURE")
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
