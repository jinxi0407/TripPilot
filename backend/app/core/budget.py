import asyncio
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from app.core.errors import ControlledError


@dataclass
class ExecutionBudget:
    clock: Callable[[], float] = time.monotonic
    seconds: float = 180
    max_tools: int = 40
    max_models: int = 30
    tools: int = 0
    models: int = 0
    cancelled: bool = False
    started: float = field(init=False)
    paused_at: float | None = None

    def __post_init__(self) -> None:
        self.started = self.clock()

    @property
    def remaining(self) -> float:
        now = self.paused_at if self.paused_at is not None else self.clock()
        return max(0.0, self.seconds - (now - self.started))

    def check(self) -> None:
        if self.cancelled:
            raise ControlledError("CANCELLED")
        if self.remaining <= 0:
            raise ControlledError("DEADLINE_EXCEEDED")

    def consume(self, kind: str) -> None:
        self.check()
        value, limit = (self.tools, self.max_tools) if kind == "tool" else (self.models, self.max_models)
        if value >= limit:
            raise ControlledError("BUDGET_EXHAUSTED")
        if kind == "tool":
            self.tools += 1
        else:
            self.models += 1

    def pause(self) -> None:
        if self.paused_at is None:
            self.paused_at = self.clock()

    def resume(self) -> None:
        if self.paused_at is not None:
            self.started += self.clock() - self.paused_at
            self.paused_at = None

    async def backoff(self) -> None:
        self.check()
        await asyncio.sleep(min(random.uniform(0.025, 0.075), self.remaining))
