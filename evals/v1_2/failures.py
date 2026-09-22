"""Ten isolated injections; no production process is stopped by this suite."""

import asyncio
import json
import socket
from contextlib import asynccontextmanager

import httpx
import uvicorn
from app.a2a.service import create_service
from app.agents.supervisor import DEMO_QUERY
from app.core.config import Settings
from app.core.errors import ControlledError
from app.core.logging import configure_logging
from app.harness.policy import RuntimePolicy
from app.mcp.server import create_server
from app.schemas.travel import Constraints
from app.services.engine import create_context, execute
from app.services.model_client import QwenClient, structured_call

from evals.v1_2.schema import DIRECTORY


@asynccontextmanager
async def cluster(delay_mcp=False):
    sockets = []
    for _ in range(3):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sock.listen(128)
        sockets.append(sock)
    ports = [s.getsockname()[1] for s in sockets]
    config = Settings(
        _env_file=None,
        protocols_enabled=True,
        protocol_fixture=True,
        rail_provider="dataset",
        memory_database=":memory:",
        mcp_url=f"http://127.0.0.1:{ports[0]}/mcp",
        a2a_transport_url=f"http://127.0.0.1:{ports[1]}",
        a2a_local_url=f"http://127.0.0.1:{ports[2]}",
        runtime_policy=RuntimePolicy(
            mcp_timeout_seconds=0.05 if delay_mcp else 1,
            a2a_timeout_seconds=5,
            health_timeout_seconds=0.2,
        ),
    )
    original = create_server(config).streamable_http_app(
        stateless_http=True, json_response=True
    )

    async def delayed(scope, receive, send):
        if scope["type"] == "http":
            await asyncio.sleep(0.3)
        await original(scope, receive, send)

    apps = [
        delayed if delay_mcp else original,
        create_service("transport", config),
        create_service("local", config),
    ]
    servers = [
        uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False))
        for app in apps
    ]
    tasks = [
        asyncio.create_task(s.serve(sockets=[sock]))
        for s, sock in zip(servers, sockets)
    ]
    while not all(s.started for s in servers):
        await asyncio.sleep(0.01)
    try:
        yield config, servers, tasks
    finally:
        for s in servers:
            s.should_exit = True
        await asyncio.gather(*tasks)
        for sock in sockets:
            sock.close()


async def protocol_fault(name, index=None, timeout=False):
    async with cluster(timeout) as (config, servers, tasks):
        if index is not None:
            servers[index].should_exit = True
            await tasks[index]
        ctx = create_context(config, mode="fixture", demo=True)
        state = await execute({"user_query": DEMO_QUERY}, ctx)
        codes = [e.code for e in ctx.runtime.events]
        expected = "MCP_FALLBACK" if index == 0 or timeout else "A2A_FALLBACK"
        detected = expected in codes and ("TIMEOUT" in codes if timeout else True)
        recovered = state["status"] in {"completed", "partial"} and bool(
            state.get("final_itinerary")
        )
        return {
            "scenario": name,
            "detected": detected,
            "recovered": recovered,
            "fallback_attempted": expected in codes,
            "fallback_success": recovered if expected in codes else None,
            "outcome": "recovered" if recovered else "safe_failure",
            "codes": list(dict.fromkeys(codes)),
            "status": state["status"],
            "runtime": ctx.runtime_status(),
        }


async def main():
    configure_logging()
    rows = []
    for name, index, timeout in [
        ("mcp_offline", 0, False),
        ("mcp_timeout", None, True),
        ("a2a_transport_offline", 1, False),
        ("a2a_local_offline", 2, False),
    ]:
        rows.append(await protocol_fault(name, index, timeout))
    ctx = create_context(Settings(_env_file=None), mode="fixture")

    async def timeout(query):
        raise ControlledError("TIMEOUT", retryable=True)

    ctx.registry.tools["amap_poi"].handler = timeout
    result = await ctx.registry.call("Local Travel", "search_poi", {"city": "杭州"})
    rows.append(
        {
            "scenario": "amap_timeout",
            "detected": result.error.code == "TIMEOUT",
            "recovered": False,
            "fallback_attempted": False,
            "fallback_success": None,
            "outcome": "safe_failure",
            "codes": [e.code for e in ctx.runtime.events],
            "reason": "持续超时按设计保留数据缺口，不伪造LIVE或静默换Mock。",
        }
    )
    for name, invalid in [
        ("qwen_transient_failure", False),
        ("invalid_structured_output", True),
    ]:
        count = [0]

        async def response(request, invalid=invalid, count=count):
            count[0] += 1
            if count[0] == 1 and not invalid:
                return httpx.Response(503)
            content = (
                "invalid JSON"
                if count[0] == 1
                else '{"origin":"杭州","destinations":["杭州"]}'
            )
            return httpx.Response(
                200,
                json={
                    "model": "qwen-plus",
                    "choices": [{"message": {"content": content}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                },
            )

        config = Settings(
            _env_file=None,
            dashscope_api_key="test-only-placeholder",
            qwen_model="qwen-plus",
        )
        ctx = create_context(config, mode="fixture")
        client = QwenClient(config, transport=httpx.MockTransport(response))
        result = await structured_call(
            client,
            {"task": "controlled_failure_test"},
            Constraints,
            ctx.budget,
            ctx.usage,
        )
        codes = [e.code for e in ctx.runtime.events]
        rows.append(
            {
                "scenario": name,
                "detected": ("INVALID_OUTPUT" if invalid else "PROVIDER_FAILURE")
                in codes,
                "recovered": result.origin == "杭州" and count[0] == 2,
                "fallback_attempted": False,
                "fallback_success": None,
                "outcome": "recovered",
                "codes": codes,
                "reason": "受控HTTP故障注入，真实共享Qwen adapter与Harness重试/结构修复；不声称本项为LIVE模型故障。",
            }
        )
    for name in [
        "duplicate_tool_loop",
        "tool_budget_exceeded",
        "forbidden_tool_request",
    ]:
        ctx = create_context(Settings(_env_file=None), mode="fixture")
        if name == "duplicate_tool_loop":
            for _ in range(3):
                result = await ctx.registry.call(
                    "Travel Planner", "search_poi", {"city": "杭州"}
                )
            expected = "DUPLICATE_TOOL_CALL"
        elif name == "tool_budget_exceeded":
            ctx.budget.max_tools = 1
            await ctx.registry.call("Travel Planner", "search_poi", {"city": "杭州"})
            result = await ctx.registry.call(
                "Travel Planner", "search_poi", {"city": "南京"}
            )
            expected = "TOOL_BUDGET_EXCEEDED"
        else:
            result = await ctx.registry.call("Travel Planner", "delete_database", {})
            expected = "TOOL_NOT_ALLOWED"
        rows.append(
            {
                "scenario": name,
                "detected": ctx.runtime.failure_reason == expected
                and result.status == "error",
                "recovered": False,
                "fallback_attempted": False,
                "fallback_success": None,
                "outcome": "safe_failure",
                "codes": [e.code for e in ctx.runtime.events],
                "reason": "按设计拒绝继续执行，不把安全停止计为任务恢复。",
            }
        )
    assert len(rows) == 10
    fallback = [r for r in rows if r["fallback_attempted"]]
    result = {
        "scenario_count": 10,
        "model_mode": "controlled injection, not LIVE quality evaluation",
        "detection": {"passed": sum(r["detected"] for r in rows), "total": 10},
        "graceful_recovery": {"passed": sum(r["recovered"] for r in rows), "total": 10},
        "fallback_success": {
            "passed": sum(r["fallback_success"] for r in fallback),
            "total": len(fallback),
        },
        "safe_failure_count": sum(r["outcome"] == "safe_failure" for r in rows),
        "scenarios": rows,
    }
    for key in ["detection", "graceful_recovery", "fallback_success"]:
        item = result[key]
        item["rate"] = item["passed"] / item["total"] if item["total"] else None
    (DIRECTORY / "failure_results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2)
    )
    print(
        json.dumps(
            {k: v for k, v in result.items() if k != "scenarios"}, ensure_ascii=False
        ),
        flush=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
