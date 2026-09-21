"""Opt-in paid Qwen benchmark. Not executed by fixture evaluation or unit tests."""

import argparse
import asyncio
import json
from datetime import datetime
from time import perf_counter

from app.agents.critic import critique
from app.agents.local_travel import research_local
from app.agents.planner import PlannerDecision, plan
from app.agents.supervisor import supervise
from app.agents.transport import research_transport
from app.core.budget import ExecutionBudget
from app.core.config import Settings
from app.core.errors import ControlledError
from app.graph.workflow import build_graph
from app.providers.fixtures import STATIONS, TZ
from app.schemas.travel import RouteQuery
from app.services.itinerary import as_place, assemble
from app.services.model_client import QwenClient, structured_call

from evals.runner import ROOT, artifact_hashes, load_cases, metrics, prepare_context


async def frozen_evidence(case) -> dict:
    ctx = prepare_context(case)
    state = {"user_query": case.query_zh}
    state.update(await supervise(state, ctx))
    if state["status"] == "needs_clarification":
        return state
    state.update(await research_transport(state, ctx))
    state.update(await research_local(state, ctx))
    # Supply all finite directed POI/station routes to the one-call baseline.
    # TripPilot can retrieve exactly the same synthetic universe using its registry.
    provider = ctx.registry.tools["amap_route"].handler
    routes = []
    for city in state["constraints"].destinations:
        places = [as_place(p) for p in state["poi_candidates"] if p.city == city]
        if city in STATIONS:
            places.append(STATIONS[city])
        for a in places:
            for b in places:
                if a.id != b.id:
                    result = await provider(RouteQuery(origin=a, destination=b))
                    routes.extend(result.data or [])
                    state["evidence"].update({e.id: e for e in result.evidence})
    state["route_data"] = routes
    return state


async def baseline(case, settings: Settings, state: dict) -> dict:
    ctx = prepare_context(case)
    ctx.budget = ExecutionBudget(max_models=1)
    ctx.model = QwenClient(settings)
    if state.get("status") == "needs_clarification":
        # This intake outcome has no dated evidence. Use one extraction call, not fabricated dates.
        state = {"user_query": case.query_zh}
        state.update(await supervise(state, ctx))
        return state, ctx
    packet = {
        key: (
            [x.model_dump(mode="json") for x in value]
            if isinstance(value, list) and value and hasattr(value[0], "model_dump")
            else value.model_dump(mode="json")
            if hasattr(value, "model_dump")
            else value
        )
        for key, value in state.items()
        if key
        in (
            "constraints",
            "city_schedule",
            "poi_candidates",
            "transport_options",
            "route_data",
            "weather_data",
        )
    }
    decision = await structured_call(
        ctx.model,
        {
            "task": "single_call_planning",
            "query": case.query_zh,
            "evidence": packet,
            "instruction": "一次性给出行程；kind 必须为 final，selections 中仅引用证据中的 ID；不能调用工具。",
        },
        PlannerDecision,
        ctx.budget,
        ctx.usage,
    )
    if decision.kind != "final":
        raise ControlledError("INVALID_OUTPUT")
    itinerary, _ = assemble(state, decision.selections, 1)
    state = {**state, "draft_itinerary": itinerary, "stop_reason": "BASELINE_NO_REPLAN"}
    state.update(await critique(state, ctx))
    return state, ctx


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-paid-model", action="store_true")
    parser.add_argument(
        "--case", action="append", help="Case IDs; default all eligible cases"
    )
    parser.add_argument("--output", default="evals/reports/model-comparison.json")
    args = parser.parse_args()
    if not args.allow_paid_model:
        raise SystemExit(
            "真实模型评估可能产生费用；仅在授权后使用 --allow-paid-model。"
        )
    settings = Settings()
    if not settings.model_ready:
        raise SystemExit(
            "请通过环境变量配置 DASHSCOPE_API_KEY 和 QWEN_CHAT_MODEL（兼容 QWEN_MODEL）；无需把密钥发送给助手。"
        )
    cases = [
        c
        for c in load_cases()
        if c.comparison_eligible and (not args.case or c.id in args.case)
    ]
    rows = []
    for case in cases:
        try:
            packet = await frozen_evidence(case)
        except ControlledError:
            packet = None
        for system in ("single-call-llm", "trippilot-qwen"):
            started = perf_counter()
            ctx = prepare_context(case)
            ctx.model = QwenClient(settings)
            try:
                if system == "single-call-llm":
                    if packet is None:
                        state = {"user_query": case.query_zh}
                        state.update(await supervise(state, ctx))
                    else:
                        state, ctx = await baseline(case, settings, packet.copy())
                else:
                    state = await build_graph(ctx, plan, critique).ainvoke(
                        {"user_query": case.query_zh}, {"recursion_limit": 64}
                    )
                status = state.get("status", "failed")
            except ControlledError as exc:
                state = {"status": "failed", "stop_reason": exc.error.code}
                status = "failed"
            values = metrics(state, ctx, case)
            if system == "single-call-llm":
                values["routing_correctness"] = None
                values["tool_selection"] = None
            rows.append(
                {
                    "case_id": case.id,
                    "system": system,
                    "model_id": settings.qwen_model,
                    "parameters": {"temperature": 0},
                    "repetition": 1,
                    "status": status,
                    "latency_ms": round((perf_counter() - started) * 1000, 3),
                    "metrics": values,
                    "fixture_override": case.fixture_overrides,
                    "note": "共享合成 Provider；错误草案注入属于独立 fixture 控制评估，本模型比较不注入。",
                }
            )
    path = ROOT / args.output
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": "measured",
                "measured_at": datetime.now(TZ).isoformat(),
                "hashes": artifact_hashes(),
                "prompt_version": "structured-planning-v1",
                "cases": rows,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"已写入 {len(rows)} 条实测结果：{path}")


if __name__ == "__main__":
    asyncio.run(main())
