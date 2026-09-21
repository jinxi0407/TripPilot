import asyncio

import httpx
import pytest

from app.agents.supervisor import DEMO_QUERY
from app.core.config import Settings
from app.core.errors import ControlledError
from app.main import create_app
from app.schemas.api import PlanRequest, RevisionRequest


@pytest.fixture
def app():
    return create_app(Settings(_env_file=None, dashscope_api_key="", qwen_model="", amap_api_key=""))


async def settle(app, key):
    await app.state.runs.store.get(key).task
    return app.state.runs.public(app.state.runs.store.get(key))


async def test_create_poll_alias_and_revision(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/plan", json={"query": DEMO_QUERY, "mode": "fixture", "demo": True})
        assert response.status_code == 202
        key = response.json()["run_id"]
        result = await settle(app, key)
        assert result["status"] == "completed"
        response = await client.get("/api/trace/" + key, params={"after_sequence": 2})
        assert all(e["sequence"] > 2 for e in response.json()["trace"])
        rev = await client.post(f"/api/v1/plans/{key}/revisions", json={"reason": "weather"})
        revised = await settle(app, rev.json()["run_id"])
        assert revised["status"] == "completed" and revised["parent_id"] == key
        assert revised["metrics"]["replanning_count"] >= 1
        assert app.state.runs.store.get(key).context.version == 1


async def test_clarification_and_errors(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/plan", json={"query": DEMO_QUERY, "mode": "fixture"})
        key = response.json()["run_id"]
        assert (await settle(app, key))["status"] == "needs_clarification"
        url = f"/api/v1/plans/{key}/clarifications"
        assert (
            await client.post(url, json={"expected_revision": 9, "answers": {"start_date": "2026-10-10"}})
        ).status_code == 409
        assert (
            await client.post(url, json={"expected_revision": 1, "answers": {"start_date": "2026-10-10"}})
        ).status_code == 202
        assert (await settle(app, key))["status"] == "completed"
        assert (await client.get("/api/v1/plans/missing")).status_code == 404
        assert (await client.post("/api/plan", json={"query": "x" * 4001})).status_code == 422
        assert (
            await client.post("/api/plan", json={"query": "10月10日杭州1日游，预算-1元"})
        ).status_code == 422


async def test_cancel_capacity_and_expiry(app):
    service = app.state.runs
    request = PlanRequest(query=DEMO_QUERY, mode="fixture", demo=True)
    a = service.create(request)
    b = service.create(request)
    with pytest.raises(ControlledError) as exc:
        service.create(request)
    assert exc.value.error.code == "CAPACITY"
    service.cancel(a.context.run_id)
    service.cancel(b.context.run_id)
    await asyncio.gather(a.task, b.task, return_exceptions=True)
    assert a.state["status"] == "cancelled"
    assert service.cancel(a.context.run_id).state["status"] == "cancelled"
    a.updated -= 3601
    with pytest.raises(ControlledError):
        service.store.get(a.context.run_id)


async def test_transport_revision(app):
    service = app.state.runs
    original = service.create(PlanRequest(query=DEMO_QUERY, mode="fixture", demo=True))
    await original.task
    revised = service.revise(original.context.run_id, RevisionRequest(reason="transport"))
    await revised.task
    assert revised.state["status"] in ("completed", "partial"), revised.state.get("validation_result")
    assert all(
        l.availability != "unavailable"
        for d in revised.state["final_itinerary"].days
        if d.rail
        for l in d.rail.legs
    )


async def test_request_body_limit_and_cors(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/plan", content=b"x" * 70000, headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 413
        response = await client.options(
            "/api/plan",
            headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST"},
        )
        assert "access-control-allow-origin" not in response.headers


async def test_status_events_are_monotonic_and_contain_tool_timings(app):
    service = app.state.runs
    record = service.create(PlanRequest(query=DEMO_QUERY, mode="fixture", demo=True))
    await record.task
    trace = service.public(record)["trace"]
    assert [e["sequence"] for e in trace] == list(range(1, len(trace) + 1))
    assert [e["timestamp"] for e in trace] == sorted(e["timestamp"] for e in trace)
    assert any(e["agent"] == "Amap Route" and e["status"] == "succeeded" for e in trace)
    assert all(e["duration_ms"] >= 0 for e in trace)
