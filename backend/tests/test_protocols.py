import asyncio
import socket

import httpx
import pytest
import uvicorn
from mcp import Client

from app.a2a.client import discover_card
from app.a2a.service import SKILLS, create_service
from app.agents.supervisor import DEMO_QUERY
from app.core.config import Settings
from app.harness.policy import RuntimePolicy
from app.mcp.schemas import CONTRACTS
from app.mcp.server import create_server
from app.services.engine import create_context, execute

ORIGINAL_HTTP = httpx.AsyncHTTPTransport.handle_async_request


@pytest.fixture
async def protocol_cluster(monkeypatch):
    async def loopback_only(self, request):
        assert request.url.host == "127.0.0.1", "protocol tests prohibit external APIs"
        return await ORIGINAL_HTTP(self, request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", loopback_only)
    sockets = []
    for _ in range(3):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sock.listen(128)
        sockets.append(sock)
    ports = [s.getsockname()[1] for s in sockets]
    settings = Settings(
        _env_file=None,
        protocols_enabled=True,
        protocol_fixture=True,
        rail_provider="dataset",
        mcp_url=f"http://127.0.0.1:{ports[0]}/mcp",
        a2a_transport_url=f"http://127.0.0.1:{ports[1]}",
        a2a_local_url=f"http://127.0.0.1:{ports[2]}",
        runtime_policy=RuntimePolicy(mcp_timeout_seconds=1, health_timeout_seconds=1),
    )
    apps = [
        create_server(settings).streamable_http_app(stateless_http=True, json_response=True),
        create_service("transport", settings),
        create_service("local", settings),
    ]
    servers = [uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False)) for app in apps]
    tasks = [asyncio.create_task(s.serve(sockets=[sock])) for s, sock in zip(servers, sockets)]
    while not all(s.started for s in servers):
        await asyncio.sleep(0.01)
    try:
        yield settings, servers, tasks
    finally:
        for s in servers:
            s.should_exit = True
        await asyncio.gather(*tasks)
        for sock in sockets:
            sock.close()


async def test_mcp_real_discovery_five_tools_and_typed_calls(protocol_cluster):
    settings, _, _ = protocol_cluster
    async with Client(settings.mcp_url) as client:
        result = await client.list_tools()
        assert {t.name for t in result.tools} == set(CONTRACTS)
        pois = await client.call_tool("search_poi", {"query": {"city": "杭州"}, "source_mode": "fixture"})
        assert not pois.is_error and pois.structured_content["result"]["data"][0]["coordinates"]
        rail = await client.call_tool(
            "search_rail", {"query": {"origin": "上海", "destination": "杭州", "date": "2026-10-10"}}
        )
        assert rail.structured_content["provider_state"] == "DATASET"
        candidates = pois.structured_content["result"]["data"]
        places = [{k: p[k] for k in ["id", "name", "city", "coordinates"]} for p in candidates[:2]]
        queries = {
            "get_weather": {"city": "杭州", "dates": ["2026-10-10"]},
            "calculate_distance": {
                "origin": places[0]["coordinates"],
                "destination": places[1]["coordinates"],
            },
            "plan_route": {"origin": places[0], "destination": places[1]},
        }
        for name, query in queries.items():
            response = await client.call_tool(name, {"query": query, "source_mode": "fixture"})
            assert not response.is_error and response.structured_content["result"]["data"]
        invalid = await client.call_tool("search_poi", {"query": {}})
        assert invalid.is_error


@pytest.mark.parametrize("role", ["transport", "local"])
async def test_a2a_real_agent_card_skills(protocol_cluster, role):
    settings, _, _ = protocol_cluster
    url = settings.a2a_transport_url if role == "transport" else settings.a2a_local_url
    async with httpx.AsyncClient() as http:
        card = await discover_card(http, url, role)
    assert set(SKILLS[role]) <= {s.id for s in card.skills}
    assert card.name == (
        "TripPilot Transport Agent" if role == "transport" else "TripPilot Local Travel Agent"
    )


async def test_supervisor_real_a2a_tasks_mcp_artifacts_and_graph(protocol_cluster):
    settings, _, _ = protocol_cluster
    context = create_context(settings, mode="fixture", demo=True)
    state = await execute({"user_query": DEMO_QUERY}, context)
    assert state["status"] == "completed" and state["validation_result"].valid
    status = context.runtime_status()
    assert status["a2a"] == {"transport": "ONLINE", "local": "ONLINE"}
    assert status["mcp"]["state"] == "CONNECTED"
    names = {t.agent for t in context.trace}
    assert {"A2A Transport Agent", "A2A Local Travel Agent", "MCP search_rail", "MCP search_poi"} <= names
    assert any(c.get("remote") for c in context.registry.calls)
    assert 0 < context.budget.tools <= 40 and 0 < context.budget.external <= 160


async def test_mcp_offline_fallback_preserves_a2a_result(protocol_cluster):
    settings, servers, tasks = protocol_cluster
    servers[0].should_exit = True
    await tasks[0]
    context = create_context(settings, mode="fixture", demo=True)
    state = await execute({"user_query": DEMO_QUERY}, context)
    assert state["status"] == "completed"
    assert context.runtime_status()["mcp"]["state"] == "FALLBACK"
    assert context.runtime_status()["a2a"]["transport"] == "ONLINE"
    assert any(e.code == "MCP_FALLBACK" for e in context.runtime.events)


async def test_a2a_offline_fallback_runs_local_specialist(protocol_cluster):
    settings, servers, tasks = protocol_cluster
    servers[1].should_exit = True
    await tasks[1]
    context = create_context(settings, mode="fixture", demo=True)
    state = await execute({"user_query": DEMO_QUERY}, context)
    assert state["status"] == "completed"
    assert context.runtime_status()["a2a"]["transport"] == "FALLBACK"
    assert any(e.code == "A2A_FALLBACK" for e in context.runtime.events)


async def test_a2a_timeout_is_bounded_and_fallback_recorded(protocol_cluster, monkeypatch):
    from app.a2a import service

    settings, _, _ = protocol_cluster
    settings.runtime_policy.a2a_timeout_seconds = 0.05
    original = service.research_transport

    async def delayed(*args):
        await asyncio.sleep(0.1)
        return await original(*args)

    monkeypatch.setattr(service, "research_transport", delayed)
    context = create_context(settings, mode="fixture", demo=True)
    state = await execute({"user_query": DEMO_QUERY}, context)
    assert state["status"] in {"failed", "partial", "completed"}
    assert any(e.code == "TIMEOUT" for e in context.runtime.events)
    assert context.budget.tools <= 40 and context.budget.external <= 160


async def test_mcp_real_timeout_uses_harness_then_local_fallback(protocol_cluster, monkeypatch):
    from app.providers.amap import MockAmapProvider

    settings, _, _ = protocol_cluster
    context = create_context(settings, mode="fixture", demo=True)
    await context.protocols.mcp.discover()
    context.runtime.policy.mcp_timeout_seconds = 0.02
    original = MockAmapProvider.pois

    async def slow_remote(self, query):
        await asyncio.sleep(0.1)
        return await original(self, query)

    # The local fallback bound method was captured before patching the server provider.
    monkeypatch.setattr(MockAmapProvider, "pois", slow_remote)
    result = await context.registry.call("Local Travel", "amap_poi", {"city": "杭州"})
    assert result.status == "ok"
    assert context.protocols.mcp.state == "FALLBACK"
    assert any(e.code == "TIMEOUT" for e in context.runtime.events)
    assert any(e.code == "MCP_FALLBACK" for e in context.runtime.events)


async def test_a2a_invalid_data_part_returns_standard_failed_task(protocol_cluster):
    from uuid import uuid4

    from a2a.client import ClientConfig, ClientFactory
    from a2a.types import a2a_pb2 as wire

    from app.a2a.service import data_part

    settings, _, _ = protocol_cluster
    async with httpx.AsyncClient() as http:
        card = await discover_card(http, settings.a2a_transport_url, "transport")
        client = ClientFactory(ClientConfig(httpx_client=http, streaming=False)).create(card)
        message = wire.Message(
            message_id=str(uuid4()), role=wire.ROLE_USER, parts=[data_part({"invalid": True})]
        )
        tasks = [
            chunk.task
            async for chunk in client.send_message(wire.SendMessageRequest(message=message))
            if chunk.HasField("task")
        ]
    assert len(tasks) == 1 and tasks[0].status.state == wire.TASK_STATE_FAILED
    assert not tasks[0].artifacts


async def test_a2a_card_endpoint_validation_prevents_redirection():
    from a2a.server.request_handlers.response_helpers import agent_card_to_dict

    from app.a2a.service import agent_card
    from app.core.errors import ControlledError

    config = Settings(_env_file=None)
    card = agent_card("transport", config)
    card.supported_interfaces[0].url = "http://untrusted.example/"
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=agent_card_to_dict(card)))
    ) as http:
        with pytest.raises(ControlledError) as error:
            await discover_card(http, config.a2a_transport_url, "transport")
    assert error.value.error.code == "INVALID_OUTPUT"


async def test_v12_seven_tools_hotels_flights_real_protocol(protocol_cluster):
    settings, _, _ = protocol_cluster
    async with Client(settings.mcp_url) as client:
        discovered = await client.list_tools()
        assert len(discovered.tools) == 7
        hotels = await client.call_tool(
            "search_hotels", {"query": {"city": "杭州"}, "source_mode": "fixture"}
        )
        assert hotels.structured_content["result"]["data"][0]["source"] == "hotel_fixture"
        flights = await client.call_tool(
            "search_flights",
            {
                "query": {"origin": "北京", "destination": "上海", "date": "2026-10-10"},
                "source_mode": "fixture",
            },
        )
        assert flights.structured_content["provider_state"] == "DATASET"
        assert flights.structured_content["result"]["data"][0]["provider_mode"] == "DATASET"


async def test_v12_specialists_return_hotel_flight_artifacts(protocol_cluster):
    from app.schemas.travel import Constraints

    settings, _, _ = protocol_cluster
    ctx = create_context(settings, mode="fixture", demo=True)
    state = await execute(
        {
            "user_query": "2026-10-10 北京到上海两天，预算4000元",
            "constraints": Constraints(recommend_hotels=True, compare_transport=True),
        },
        ctx,
    )
    assert state["flight_options"] and state["accommodation"] and state["transport_comparisons"]
    assert ctx.runtime_status()["a2a"] == {"transport": "ONLINE", "local": "ONLINE"}
    names = {t.agent for t in ctx.trace}
    assert {"MCP search_flights", "MCP search_hotels"} <= names
    assert len(ctx.runtime_status()["mcp"]["tools"]) == 7
