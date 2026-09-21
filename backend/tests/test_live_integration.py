import json
import logging
from datetime import date

import httpx
import pytest

from app.agents.local_travel import research_local
from app.agents.supervisor import DEMO_QUERY, parse_fixture
from app.core.config import Settings
from app.core.errors import ControlledError
from app.core.logging import NoQueryString
from app.main import create_app
from app.providers.amap import AmapProvider
from app.schemas.api import PlanRequest, RevisionRequest
from app.schemas.travel import Constraints, POIQuery
from app.services.engine import create_context, execute
from app.services.model_client import ModelReply, QwenClient
from app.services.runs import RunService


async def test_actual_model_and_status_not_inferred_from_configuration():
    def handle(request):
        assert json.loads(request.content)["enable_thinking"] is False
        return httpx.Response(
            200,
            json={
                "model": "qwen-test-actual",
                "choices": [
                    {"message": {"content": '{"ok":true}', "reasoning_content": "PRIVATE_REASONING_MARKER"}}
                ],
            },
        )

    client = QwenClient(
        Settings(dashscope_api_key="fake", qwen_model="qwen-test"), httpx.MockTransport(handle)
    )
    assert client.status == "PENDING"
    reply = await client.complete({}, {})
    assert client.status == "LIVE" and client.actual_model == "qwen-test-actual"
    assert "PRIVATE_REASONING_MARKER" not in reply.model_dump_json()


async def test_amap_live_source_and_safe_diagnostics():
    provider = AmapProvider(
        "fake",
        httpx.MockTransport(
            lambda r: httpx.Response(
                200, json={"status": "1", "pois": [{"id": "real-id", "name": "博物院", "location": "120,30"}]}
            )
        ),
    )
    assert provider.status == "PENDING"
    result = await provider.pois(POIQuery(city="杭州"))
    assert provider.status == "LIVE" and result.evidence[0].source == "amap_live"
    assert result.data[0].environment == "indoor"
    provider.transport = httpx.MockTransport(
        lambda r: httpx.Response(
            200, json={"status": "0", "infocode": "10009", "info": "fake-credential-in-raw-error"}
        )
    )
    with pytest.raises(ControlledError) as error:
        await provider.pois(POIQuery(city="杭州"))
    assert error.value.error.provider_code == "10009"
    assert provider.status == "FAILED" and "fake-credential" not in str(error.value)


async def test_map_configuration_and_proxy_boundaries():
    app = create_app(Settings(vite_amap_js_key="js-marker", vite_amap_security_code="security-marker"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        result = await client.get("/api/map/config")
        assert result.json()["configured"]
        assert "js-marker" not in result.text and "security-marker" not in result.text
        assert (await client.get("/_AMapService/https://evil.example")).status_code == 422
        health = (await client.get("/health")).json()
        assert health["provider_status"]["qwen"]["state"] == "UNCONFIGURED"


def test_access_log_removes_credential_query():
    record = logging.LogRecord(
        "uvicorn.access",
        20,
        "",
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("local", "GET", "/_AMapService/v4/maps?key=secret&jscode=secret", "1.1", 200),
        None,
    )
    assert NoQueryString().filter(record)
    assert "secret" not in record.getMessage()


async def test_live_rain_is_separate_simulation_evidence():
    context = create_context(Settings(), mode="fixture", scenario="rain")
    context.model.name = "qwen"  # Exercise mixed-source handling without any real model or network.
    constraints = Constraints(origin="杭州", destinations=["杭州"], days=1, start_date=date(2026, 10, 10))
    result = await research_local(
        {"constraints": constraints, "city_schedule": ["杭州"], "travel_dates": constraints.dates}, context
    )
    weather = result["weather_data"][0]
    assert weather.severity == "severe"
    assert result["evidence"][weather.evidence_id].source == "weather_simulation"
    assert result["evidence"][weather.evidence_id].source_kind == "mock"


async def test_live_revision_does_not_silently_change_model():
    service = RunService(Settings())
    original = service.create(PlanRequest(query=DEMO_QUERY, mode="fixture", demo=True))
    await original.task
    original.request.mode = "live"
    revised = service.revise(original.context.run_id, RevisionRequest(reason="weather"))
    assert revised.context.model.name == "qwen" and revised.context.simulated_rain
    await revised.task
    assert revised.state["status"] == "failed"
    assert service.public(revised)["provider_status"]["qwen"]["state"] == "FAILED"
    await service.close()


async def test_model_final_waits_for_missing_routes():
    class DecisionModel:
        name = "qwen"
        final_attempts = 0

        async def complete(self, payload, schema):
            if payload["task"] == "extract_constraints":
                return ModelReply(
                    content=json.dumps(parse_fixture(DEMO_QUERY, date(2026, 10, 1)), default=str)
                )
            if self.final_attempts and payload["missing_routes"]:
                result = {"kind": "action", "tool": "amap_route", "arguments": payload["missing_routes"][0]}
            else:
                self.final_attempts += 1
                result = {"kind": "final", "selections": payload["suggested_selections"]}
            return ModelReply(content=json.dumps(result, default=str))

    context = create_context(Settings(), mode="fixture", demo=True)
    context.model = DecisionModel()
    result = await execute({"user_query": DEMO_QUERY}, context)
    assert result["status"] == "completed"
    assert context.model.final_attempts >= 2
    assert not any(i.type == "LOCAL_ROUTE_FEASIBILITY" for i in result["validation_result"].issues)


async def test_map_proxy_injects_security_only_upstream(monkeypatch):
    from app.api import maps

    seen = []

    def handle(request):
        seen.append(request.url.params.get("jscode"))
        assert request.url.params["key"] == "server-js-marker"
        return httpx.Response(200, json={"status": "1", "styles": []})

    original_client = httpx.AsyncClient
    app = create_app(
        Settings(vite_amap_js_key="server-js-marker", vite_amap_security_code="private-code-marker")
    )
    async with original_client(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        monkeypatch.setattr(
            maps.httpx,
            "AsyncClient",
            lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs),
        )
        response = await client.get("/_AMapService/v4/map/styles?key=untrusted&jscode=untrusted")
    assert response.status_code == 200 and seen == ["private-code-marker"]
    assert "private-code-marker" not in response.text and "server-js-marker" not in response.text


@pytest.mark.parametrize(
    ("body", "callback", "expected_type"),
    [
        (b'initCallback({"status":1})', "initCallback", "application/javascript"),
        (b'{"status":0}', "initCallback", "application/octet-stream"),
        (b'otherCallback({"status":1})', "initCallback", "application/octet-stream"),
    ],
)
async def test_map_proxy_jsonp_mime_without_disabling_nosniff(monkeypatch, body, callback, expected_type):
    from app.api import maps

    original_client = httpx.AsyncClient
    app = create_app(Settings(vite_amap_js_key="test-js", vite_amap_security_code="test-security"))
    async with original_client(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        monkeypatch.setattr(
            maps.httpx,
            "AsyncClient",
            lambda **kwargs: original_client(
                transport=httpx.MockTransport(
                    lambda r: httpx.Response(
                        200, content=body, headers={"content-type": "application/octet-stream"}
                    )
                ),
                **kwargs,
            ),
        )
        response = await client.get("/_AMapService/v3/log/init", params={"callback": callback})
    assert response.headers["content-type"].startswith(expected_type)
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.content == body


@pytest.mark.parametrize(
    ("query", "names", "expected"),
    [
        ("拙政园", ["拙政园-浮翠阁", "拙政园"], "拙政园"),
        ("浙江省博物馆孤山馆", ["浙江省博物馆(孤山馆区)", "浙江自然博物院"], "浙江省博物馆(孤山馆区)"),
    ],
)
async def test_poi_ranking_prefers_exact_attraction_and_preserves_provider_relevance(query, names, expected):
    provider = AmapProvider(
        "test-key",
        httpx.MockTransport(
            lambda r: httpx.Response(
                200,
                json={"status": "1", "pois": [
                    {"id": str(i), "name": name, "location": "120,30"} for i, name in enumerate(names)
                ]},
            )
        ),
    )
    result = await provider.pois(POIQuery(city="杭州", keywords=query, limit=1))
    assert result.data[0].name == expected


async def test_real_adapter_timeout_is_retried_within_structured_call_budget():
    from pydantic import BaseModel

    from app.core.budget import ExecutionBudget
    from app.services.model_client import structured_call

    class Reply(BaseModel):
        ok: bool

    attempts = []

    def handle(request):
        attempts.append(1)
        assert request.extensions["timeout"]["read"] == 30
        if len(attempts) == 1:
            raise httpx.ReadTimeout("sanitized test timeout")
        return httpx.Response(200, json={"model": "qwen-test", "choices": [{"message": {"content": '{"ok":true}'}}]})

    client = QwenClient(Settings(dashscope_api_key="test-key", qwen_model="qwen-test"), httpx.MockTransport(handle))
    usage = []
    result = await structured_call(client, {}, Reply, ExecutionBudget(), usage)
    assert result.ok and len(attempts) == len(usage) == 2
    assert client.status == "LIVE"
