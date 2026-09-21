import asyncio
import logging

from pydantic import ValidationError

from app.agents.supervisor import parse_fixture
from app.core.config import Settings
from app.core.errors import ControlledError
from app.persistence.store import TERMINAL, RunRecord, RunStore
from app.providers.fixtures import FIXED_NOW
from app.schemas.api import ClarificationRequest, PlanRequest, RevisionRequest
from app.schemas.travel import Constraints
from app.services.engine import create_context, execute


class RunService:
    def __init__(self, settings: Settings, store: RunStore | None = None) -> None:
        self.settings = settings
        self.store = store or RunStore()

    def create(self, request: PlanRequest, parent: RunRecord | None = None) -> RunRecord:
        if (
            request.scenario != "normal"
            and request.mode != "fixture"
            and not (parent and request.scenario == "rain")
        ):
            raise ControlledError("INVALID_INPUT")
        if request.mode != "live" and not self.settings.model_ready:
            # Validate obvious request errors before allocating a background job.
            parsed = parse_fixture(request.query, FIXED_NOW.date())
            if request.constraints:
                parsed.update(request.constraints.model_dump(exclude_unset=True))
            try:
                Constraints.model_validate(parsed)
            except ValidationError:
                raise ControlledError("INVALID_INPUT") from None
        context = create_context(self.settings, request.mode, request.demo, request.scenario)
        if parent:
            context.version = parent.context.version + 1
        state = {"user_query": request.query, "status": "queued", "replanning_count": 0, "evidence": {}}
        if request.constraints:
            state["constraints"] = request.constraints
        record = RunRecord(request, context, state, parent_id=parent.context.run_id if parent else None)
        self.store.add(record)
        self.launch(record)
        return record

    def launch(self, record: RunRecord) -> None:
        record.task = asyncio.create_task(self._work(record))

    async def _work(self, record: RunRecord) -> None:
        record.state["status"] = "running"
        try:
            result = await execute(record.state, record.context)
            if record.state.get("status") != "cancelled":
                record.state = result
            if record.state.get("status") == "needs_clarification" or record.state.get("status") in TERMINAL:
                record.context.budget.pause()
        except asyncio.CancelledError:
            record.state["status"] = "cancelled"
        except Exception:  # noqa: BLE001 - sanitize unexpected failures at the background-task boundary
            # Top-level task boundary: log only a safe event code, never upstream text.
            logging.getLogger("trippilot").error("run_failed", extra={"event_code": "run_failed"})
            record.state.update(status="failed", stop_reason="PROVIDER_FAILURE")
        finally:
            record.updated = self.store.clock()
            self.store.prune()

    def clarify(self, key: str, request: ClarificationRequest) -> RunRecord:
        record = self.store.get(key)
        if (
            record.state.get("status") != "needs_clarification"
            or record.revision != request.expected_revision
        ):
            raise ControlledError("CONFLICT")
        self.store.capacity()
        data = record.state["constraints"].model_dump()
        data.update(request.answers.model_dump(exclude_unset=True))
        try:
            constraints = Constraints.model_validate(data)
        except ValidationError:
            raise ControlledError("INVALID_INPUT") from None
        record.state["constraints"] = constraints
        record.revision += 1
        record.state["status"] = "queued"
        record.context.budget.resume()
        self.launch(record)
        return record

    def revise(self, key: str, request: RevisionRequest) -> RunRecord:
        parent = self.store.get(key)
        if parent.state.get("status") not in TERMINAL or not parent.state.get("final_itinerary"):
            raise ControlledError("CONFLICT")
        data = parent.state["constraints"].model_dump()
        if request.constraints:
            data.update(request.constraints.model_dump(exclude_unset=True))
        try:
            constraints = Constraints.model_validate(data)
        except ValidationError:
            raise ControlledError("INVALID_INPUT") from None
        scenario = parent.request.scenario
        if request.reason == "weather":
            scenario = "rain"
        if parent.request.mode == "fixture":
            if request.reason == "weather":
                scenario = "rain"
            elif request.reason == "transport":
                scenario = "transport"
        new_request = PlanRequest(
            query=request.query or parent.request.query,
            constraints=constraints,
            mode=parent.request.mode,
            demo=parent.request.demo,
            scenario=scenario,
        )
        return self.create(new_request, parent)

    def cancel(self, key: str) -> RunRecord:
        record = self.store.get(key)
        if record.state.get("status") not in TERMINAL:
            record.state["status"] = "cancelled"
            record.context.budget.cancelled = True
            record.context.emit("System", "failed", "任务已取消")
            if record.task:
                record.task.cancel()
            record.updated = self.store.clock()
        return record

    def public(self, record: RunRecord, after_sequence: int = 0) -> dict:
        state = record.state
        usage = record.context.usage
        token_total = (
            sum(u.input_tokens + u.output_tokens for u in usage if u) if usage and all(usage) else None
        )
        error = ControlledError(state["stop_reason"]).error.model_dump() if state.get("stop_reason") else None

        def dump(value):
            return value.model_dump(mode="json") if value is not None else None

        return {
            "run_id": record.context.run_id,
            "task_id": record.context.run_id,
            "status": state.get("status", "queued"),
            "revision": record.revision,
            "itinerary_version": record.context.version,
            "parent_id": record.parent_id,
            "mode": record.context.model.name,
            "provider_status": record.context.provider_status(),
            "runtime_status": record.context.runtime_status(),
            "simulated_rain": record.context.simulated_rain,
            "poll_url": f"/api/v1/plans/{record.context.run_id}",
            "constraints": dump(state.get("constraints")),
            "questions": state.get("questions", []),
            "itinerary": dump(state.get("final_itinerary")),
            "validation": dump(state.get("validation_result")),
            "trace": [e.model_dump(mode="json") for e in record.context.trace if e.sequence > after_sequence],
            "evidence": [e.model_dump(mode="json") for e in state.get("evidence", {}).values()],
            "metrics": {
                "agent_steps": record.context.steps,
                "tool_attempts": record.context.budget.tools,
                "model_attempts": record.context.budget.models,
                "tokens": token_total,
                "replanning_count": state.get("replanning_count", 0),
            },
            "error": error,
        }

    async def close(self) -> None:
        tasks = []
        for record in list(self.store.runs.values()):
            if record.task and not record.task.done():
                self.cancel(record.context.run_id)
                tasks.append(record.task)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
