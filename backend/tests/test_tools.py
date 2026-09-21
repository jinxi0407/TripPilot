import asyncio
from datetime import date

import httpx
import pytest

from app.core.budget import ExecutionBudget
from app.core.errors import ControlledError
from app.providers.amap import AmapProvider, MockAmapProvider
from app.providers.fixtures import STATIONS
from app.providers.rail import DatasetRailProvider, MockRailProvider, RealRailProvider
from app.schemas.travel import DistanceQuery, POIQuery, RailQuery, RouteQuery, ToolResult, WeatherQuery
from app.tools.registry import Tool, ToolRegistry
from app.tools.travel import create_registry


@pytest.mark.parametrize("provider", [MockRailProvider(), DatasetRailProvider()])
async def test_rail_contract(provider):
    query = RailQuery(origin="上海", destination="杭州", date=date(2026, 10, 10))
    result = await provider.search(query)
    assert result.status == "ok" and len(result.data) >= 1
    leg = result.data[0].legs[0]
    assert leg.price > 0 and leg.duration > 0 and leg.arrival_time > leg.departure_time
    assert leg.availability == "unknown" and result.evidence[0].source_kind != "live"


async def test_dataset_transfer_and_real_unavailable():
    q = RailQuery(origin="上海", destination="南京", date=date(2026, 10, 10))
    result = await DatasetRailProvider().search(q)
    assert any(not r.direct and len(r.transfer_minutes) == 1 for r in result.data)
    assert (await RealRailProvider().search(q)).status == "unavailable"


async def test_mock_poi_restaurant_weather_distance():
    p = MockAmapProvider()
    assert (await p.pois(POIQuery(city="杭州"))).data[0].coordinates.system == "GCJ-02"
    assert (await p.pois(POIQuery(city="杭州", category="restaurant"))).data[0].category == "restaurant"
    assert (await p.pois(POIQuery(city="未知"))).status == "empty"
    assert (await p.weather(WeatherQuery(city="杭州", dates=[date(2026, 12, 1)]))).status == "unavailable"
    q = DistanceQuery(origin=STATIONS["上海"].coordinates, destination=STATIONS["杭州"].coordinates)
    assert (await p.distance(q)).data[0].meters > 100000


@pytest.mark.parametrize("mode", ["walk", "drive", "transit"])
async def test_routes(mode):
    p = MockAmapProvider()
    pois = (await p.pois(POIQuery(city="杭州"))).data
    route = (await p.route(RouteQuery(origin=pois[0], destination=pois[1], mode=mode))).data[0]
    assert route.duration > 0 and route.mode == mode


async def test_registry_permission_validation_cache():
    budget = ExecutionBudget()
    registry = create_registry(MockRailProvider(), MockAmapProvider(), budget)
    assert (await registry.call("Transport", "amap_poi", {"city": "杭州"})).error.code == "TOOL_DENIED"
    assert (await registry.call("Local Travel", "amap_poi", {})).error.code == "INVALID_INPUT"
    assert budget.tools == 0
    await registry.call("Local Travel", "amap_poi", {"city": "杭州"})
    await registry.call("Local Travel", "amap_poi", {"city": "杭州"})
    assert budget.tools == 1 and registry.calls[-1]["cached"]


async def test_retry_duplicate_and_budget():
    budget = ExecutionBudget()
    registry = create_registry(MockRailProvider(), MockAmapProvider(outage=True), budget)
    assert (await registry.call("Local Travel", "amap_poi", {"city": "杭州"})).error.code == "TIMEOUT"
    assert budget.tools == 2
    assert (
        await registry.call("Local Travel", "amap_poi", {"city": "杭州"})
    ).error.code == "DUPLICATE_ACTION"
    budget.tools = 40
    assert (
        await registry.call("Local Travel", "amap_poi", {"city": "南京"})
    ).error.code == "BUDGET_EXHAUSTED"


async def test_real_timeout_and_output_validation():
    async def slow(q):
        await asyncio.sleep(1)

    registry = ToolRegistry(
        [Tool("slow", POIQuery, ToolResult[list], slow, frozenset({"Local Travel"}), timeout=0.001)],
        ExecutionBudget(),
    )
    assert (await registry.call("Local Travel", "slow", {"city": "杭州"})).error.code == "TIMEOUT"
    assert registry.budget.tools == 2

    async def malformed(q):
        return {"status": "invented"}

    registry.tools["slow"].handler = malformed
    assert (await registry.call("Local Travel", "slow", {"city": "南京"})).error.code == "INVALID_OUTPUT"


async def test_amap_live_poi_normalization_and_auth():
    data = {"status": "1", "pois": [{"id": "1", "name": "博物馆", "location": "120.1,30.2"}]}
    p = AmapProvider("test-key", httpx.MockTransport(lambda r: httpx.Response(200, json=data)))
    result = await p.pois(POIQuery(city="杭州"))
    assert result.data[0].ticket_price is None and result.data[0].opening_start is None
    assert result.evidence[0].source_kind == "live"
    p = AmapProvider(
        "test-key",
        httpx.MockTransport(
            lambda r: httpx.Response(200, json={"status": "0", "infocode": "10001", "info": "test-key"})
        ),
    )
    with pytest.raises(ControlledError) as exc:
        await p.pois(POIQuery(city="杭州"))
    assert exc.value.error.code == "AUTH_REQUIRED" and "test-key" not in str(exc.value)


@pytest.mark.parametrize("mode", ["walk", "drive", "transit"])
async def test_amap_live_route_and_empty(mode):
    data = {
        "status": "1",
        "route": {
            "paths": [{"duration": "600", "distance": "1000"}],
            "transits": [{"duration": "1200", "distance": "2000", "cost": "4"}],
        },
    }
    p = AmapProvider("test-key", httpx.MockTransport(lambda r: httpx.Response(200, json=data)))
    q = RouteQuery(origin=STATIONS["杭州"], destination=STATIONS["上海"], mode=mode)
    result = await p.route(q)
    assert result.data[0].duration == (20 if mode == "transit" else 10)
    p = AmapProvider(
        "test-key", httpx.MockTransport(lambda r: httpx.Response(200, json={"status": "1", "route": {}}))
    )
    assert (await p.route(q)).status == "unavailable"


async def test_amap_live_weather_distance_malformed():
    def handler(req):
        if "weather" in req.url.path:
            return httpx.Response(
                200,
                json={
                    "status": "1",
                    "forecasts": [{"casts": [{"date": "2026-10-10", "dayweather": "暴雨"}]}],
                },
            )
        return httpx.Response(200, json={"status": "1", "results": [{"distance": "1000", "info": "1"}]})

    p = AmapProvider("test-key", httpx.MockTransport(handler))
    assert (await p.weather(WeatherQuery(city="杭州", dates=[date(2026, 10, 10)]))).data[
        0
    ].severity == "severe"
    q = DistanceQuery(origin=STATIONS["上海"].coordinates, destination=STATIONS["杭州"].coordinates)
    assert (await p.distance(q)).data[0].meters == 1000
    p = AmapProvider(
        "test-key", httpx.MockTransport(lambda r: httpx.Response(200, json={"status": "1", "pois": [{}]}))
    )
    with pytest.raises(ControlledError):
        await p.pois(POIQuery(city="杭州"))
