import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from app.core.errors import ControlledError
from app.graph.state import AgentState
from app.schemas.api import PlanRequest
from app.services.context import RunContext

TERMINAL = {"completed", "partial", "conflict", "failed", "cancelled"}


@dataclass
class RunRecord:
    request: PlanRequest
    context: RunContext
    state: AgentState
    revision: int = 1
    parent_id: str | None = None
    updated: float = field(default_factory=time.monotonic)
    task: asyncio.Task | None = None


class RunStore:
    def __init__(self, clock: Callable[[], float] = time.monotonic, max_active: int = 2) -> None:
        self.runs: dict[str, RunRecord] = {}
        self.clock = clock
        self.max_active = max_active

    def prune(self) -> None:
        expired = [
            key
            for key, r in self.runs.items()
            if r.state.get("status") not in ("running", "queued") and self.clock() - r.updated >= 3600
        ]
        for key in expired:
            del self.runs[key]
        terminal = sorted(
            [(key, r) for key, r in self.runs.items() if r.state.get("status") in TERMINAL],
            key=lambda x: x[1].updated,
        )
        for key, _ in terminal[:-50]:
            del self.runs[key]

    def capacity(self) -> None:
        self.prune()
        if sum(r.state.get("status") in ("running", "queued") for r in self.runs.values()) >= self.max_active:
            raise ControlledError("CAPACITY")
        if sum(r.state.get("status") == "needs_clarification" for r in self.runs.values()) >= 50:
            raise ControlledError("CAPACITY")

    def get(self, key: str) -> RunRecord:
        self.prune()
        if key not in self.runs:
            raise ControlledError("NOT_FOUND")
        return self.runs[key]

    def add(self, record: RunRecord) -> None:
        self.capacity()
        record.updated = self.clock()
        self.runs[record.context.run_id] = record
