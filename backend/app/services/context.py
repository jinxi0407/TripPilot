from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from app.core.budget import ExecutionBudget
from app.core.config import Settings
from app.graph.state import TraceEvent
from app.providers.fixtures import FIXED_NOW
from app.services.model_client import ModelClient, Usage
from app.tools.registry import ToolRegistry


@dataclass
class RunContext:
    model: ModelClient
    registry: ToolRegistry
    budget: ExecutionBudget
    run_id: str = field(default_factory=lambda: str(uuid4()))
    now: datetime = FIXED_NOW
    version: int = 1
    trace: list[TraceEvent] = field(default_factory=list)
    usage: list[Usage | None] = field(default_factory=list)
    steps: dict[str, int] = field(default_factory=dict)
    demo: bool = False
    local_provider: Any = field(default=None, repr=False)
    rail_mode: str = "mock"
    simulated_rain: bool = False
    settings: Settings = field(default_factory=Settings, repr=False)
    source_mode: str = "fixture"
    memory_status: dict = field(default_factory=lambda: {"state": "DISABLED"})
    memory_preferences: dict = field(default_factory=dict)
    protocols: Any = field(default=None, repr=False)
    remote_provider_status: dict = field(default_factory=dict)

    def provider_status(self) -> dict:
        amap_failures = [
            r["status"]
            for r in self.registry.calls
            if r["tool"].startswith("amap_")
            and r["status"]
            in {"AUTH_REQUIRED", "TIMEOUT", "RATE_LIMITED", "PROVIDER_FAILURE", "INVALID_OUTPUT"}
        ]
        rail_calls = [r for r in self.registry.calls if r["tool"] == "rail_search"]
        rail_state = (
            "PENDING"
            if not rail_calls
            else (self.rail_mode.upper() if any(r["status"] == "ok" for r in rail_calls) else "FAILED")
        )
        status = {
            "qwen": {
                "state": getattr(self.model, "status", "MOCK"),
                "model": getattr(self.model, "actual_model", None),
                "error_code": getattr(self.model, "error_code", None),
            },
            "amap": {
                "state": "FAILED"
                if amap_failures and hasattr(self.local_provider, "status")
                else getattr(self.local_provider, "status", "MOCK"),
                "error_code": getattr(self.local_provider, "error_code", None)
                or (amap_failures[-1] if amap_failures else None),
            },
            "rail": {"state": rail_state if rail_state != "REAL" else "FAILED"},
        }

        for key, name, default in [
            ("flight", "flight_search", self.settings.flight_provider.upper()),
            ("hotel", "amap_hotels", getattr(self.local_provider, "status", "MOCK")),
        ]:
            calls = [r for r in self.registry.calls if r["tool"] == name]
            status[key] = {
                "state": default
                if calls and any(r["status"] in {"ok", "empty"} for r in calls)
                else ("FAILED" if calls else "PENDING")
            }
        status.update(self.remote_provider_status)
        return status

    def runtime_status(self) -> dict:
        protocols = (
            self.protocols.snapshot()
            if self.protocols
            else {
                "mcp": {"state": "DISABLED", "tools": []},
                "a2a": {"transport": "DISABLED", "local": "DISABLED"},
            }
        )
        return {**protocols, "harness": self.runtime.snapshot(), "memory": self.memory_status}

    @property
    def runtime(self):
        return self.registry.runtime

    def __post_init__(self) -> None:
        self.budget.runtime = self.runtime

        def runtime_event(event):
            self.emit(event.component, event.status, event.code.replace("_FALLBACK", " FALLBACK"))

        self.runtime.on_event = runtime_event
        labels = {
            "rail_search": "Rail Search",
            "flight_search": "Flight Search",
            "amap_hotels": "Hotel Search",
            "amap_poi": "Amap POI",
            "amap_route": "Amap Route",
            "amap_distance": "Amap Distance",
            "amap_weather": "Amap Weather",
        }
        summaries = {
            "rail_search": "铁路信息查询",
            "flight_search": "航空候选查询",
            "amap_hotels": "住宿候选查询",
            "amap_poi": "本地景点查询",
            "amap_route": "景点间交通路线查询",
            "amap_distance": "地理距离查询",
            "amap_weather": "目的地天气查询",
        }

        def tool_event(name: str, status: str, duration_ms: int) -> None:
            self.emit(
                labels[name],
                status,
                summaries[name]
                + {"running": "进行中", "succeeded": "已完成", "failed": "未完成，保留数据缺口"}[status],
                duration_ms,
            )

        self.registry.on_event = tool_event

    def emit(self, agent: str, status: str, summary: str, duration_ms: int = 0) -> None:
        # Summaries are application-authored templates, never model-supplied reasoning.
        self.trace.append(
            TraceEvent(
                sequence=len(self.trace) + 1,
                run_id=self.run_id,
                itinerary_version=self.version,
                agent=agent,
                status=status,
                summary=summary,
                timestamp=self.now + timedelta(seconds=self.budget.seconds - self.budget.remaining),
                duration_ms=max(0, duration_ms),
            )
        )
