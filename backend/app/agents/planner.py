import asyncio
from typing import Any, Literal

from pydantic import Field, model_validator

from app.core.errors import ControlledError
from app.graph.state import AgentState
from app.schemas.travel import POI, RailOption, RouteOption, Schema, WeatherRecord
from app.services.context import RunContext
from app.services.itinerary import DaySelection, assemble, default_selections
from app.services.model_client import MockModelClient, structured_call


class PlannerDecision(Schema):
    kind: Literal["action", "final"]
    tool: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    selections: list[DaySelection] = Field(default_factory=list, max_length=7)

    @model_validator(mode="after")
    def valid_decision(self) -> "PlannerDecision":
        if self.kind == "action" and not self.tool:
            raise ValueError("action requires tool")
        if self.kind == "final" and not self.selections:
            raise ValueError("final requires selections")
        return self


async def plan(state: AgentState, context: RunContext) -> dict:
    context.emit("Travel Planner", "running", "正在组合景点、交通与每日节奏")
    started = context.budget.clock()
    policy = context.runtime.policy
    scope = "planner-" + str(len(context.trace))
    pass_steps = 0
    working = dict(state)
    selections = default_selections(state)
    draft, missing = assemble(working, selections, context.version)
    observations = []
    stop_reason = None

    def consume_step() -> None:
        nonlocal pass_steps
        if pass_steps >= policy.max_react_steps:
            raise ControlledError("MAX_STEPS")
        if context.budget.clock() - started >= policy.react_timeout_seconds:
            raise ControlledError("DEADLINE_EXCEEDED")
        context.runtime.step(scope)
        pass_steps += 1
        context.steps["Travel Planner"] = context.steps.get("Travel Planner", 0) + 1

    def mock_decision(payload: dict) -> dict:
        if missing:
            return {"kind": "action", "tool": "amap_route", "arguments": missing[0].model_dump(mode="json")}
        return {"kind": "final", "selections": [s.model_dump() for s in selections]}

    client = (
        MockModelClient(mock_decision)
        if isinstance(context.model, MockModelClient) and context.model.responder is None
        else context.model
    )
    try:
        async with asyncio.timeout(min(policy.react_timeout_seconds, context.budget.remaining)):
            while pass_steps < policy.max_react_steps:
                context.budget.check()
                decision = await structured_call(
                    client,
                    {
                        "task": "plan_itinerary",
                        "constraints": state["constraints"].model_dump(mode="json"),
                        "city_schedule": state["city_schedule"],
                        "tools": context.registry.schemas("Travel Planner"),
                        "pois": [p.model_dump(mode="json") for p in working.get("poi_candidates", [])],
                        "rails": [r.model_dump(mode="json") for r in working.get("transport_options", [])],
                        "weather": [w.model_dump(mode="json") for w in working.get("weather_data", [])],
                        "routes": [r.model_dump(mode="json") for r in working.get("route_data", [])],
                        "suggested_selections": [s.model_dump() for s in selections],
                        "missing_routes": [q.model_dump(mode="json") for q in missing],
                        "feedback": state["validation_result"].model_dump()
                        if state.get("validation_result")
                        else None,
                        "observations": observations,
                        "weather_repair": {
                            "required": state.get("replanning_count", 0) > 0
                            and any(w.severity == "severe" for w in working.get("weather_data", [])),
                            "rule": "暴雨修复时，每个受影响日期都只能使用室内候选。安全优先于景点去重：候选有限时允许同城多天再次参观同一室内场馆，不能换回户外景点。遵循 suggested_selections。",
                        },
                        "instruction": "先检查 missing_routes：非空则本步必须返回 kind=action，复制其中第一个查询的完整参数调用 amap_route，不要返回 final，不要重复已有路线。missing_routes 为空时返回 kind=final。优先采用 suggested_selections，它已按真实交通安排轻松节奏；跨城市移动当天只安排一个活动，避免超过市内交通120分钟。完成时只引用已有 POI/rail ID，不得遗漏城市或铁路，每天至少一个活动。Critic 反馈严重天气时只能选 environment=indoor。未知开放时间和预报不能靠重复查询解决。预算单位为分。",
                    },
                    PlannerDecision,
                    context.budget,
                    context.usage,
                    consume_step,
                )
                if decision.kind == "final":
                    draft, missing = assemble(working, decision.selections, context.version)
                    selections = decision.selections
                    if missing and not isinstance(client, MockModelClient):
                        observations.append(
                            {
                                "status": "missing_routes",
                                "instruction": "最终选择还有缺失路线，请先调用 missing_routes 中的路线查询再提交。",
                            }
                        )
                        continue
                    context.emit("Travel Planner", "succeeded", "行程草案已生成，交由 Critic 校验")
                    break
                context.emit("Travel Planner", "running", "正在查询补充证据，完善景点间交通")
                result = await context.registry.call("Travel Planner", decision.tool, decision.arguments)
                observations.append(
                    {
                        "tool": decision.tool,
                        "status": result.status,
                        "error": result.error.model_dump() if result.error else None,
                        "data": [v.model_dump(mode="json") for v in result.data] if result.data else [],
                    }
                )
                evidence = dict(working.get("evidence", {}))
                evidence.update({e.id: e for e in result.evidence})
                working["evidence"] = evidence
                fields = {
                    "amap_route": ("route_data", RouteOption),
                    "amap_poi": ("poi_candidates", POI),
                    "rail_search": ("transport_options", RailOption),
                    "amap_weather": ("weather_data", WeatherRecord),
                }
                if result.data and decision.tool in fields:
                    field, _ = fields[decision.tool]
                    working[field] = list(working.get(field, [])) + result.data
                draft, missing = assemble(working, selections, context.version)
                if result.error and result.error.code in (
                    "DUPLICATE_ACTION",
                    "BUDGET_EXHAUSTED",
                    "DEADLINE_EXCEEDED",
                ):
                    raise ControlledError(result.error.code)
            else:
                raise ControlledError("MAX_STEPS")
    except TimeoutError:
        stop_reason = "DEADLINE_EXCEEDED"
    except ControlledError as exc:
        stop_reason = exc.error.code
    if stop_reason:
        context.runtime.record("ReAct", stop_reason)
        draft.warnings.append("规划触及执行限制，当前展示可用草案，部分信息可能未完成。")
        context.emit("Travel Planner", "failed", "已触发执行保护，保留当前草案进行校验")
    return {
        **{
            field: working.get(field, [])
            for field in ("route_data", "poi_candidates", "transport_options", "weather_data")
        },
        "evidence": working.get("evidence", {}),
        "draft_itinerary": draft,
        "stop_reason": stop_reason,
    }
