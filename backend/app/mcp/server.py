from typing import Literal

from mcp.server import MCPServer

from app.core.config import Settings
from app.core.errors import ControlledError
from app.core.logging import configure_logging
from app.harness.budget import ExecutionBudget
from app.harness.runtime import RuntimeHarness
from app.mcp.schemas import CONTRACTS, MCPReply
from app.providers.amap import AmapProvider, MockAmapProvider
from app.providers.flight import DatasetFlightProvider, RealFlightProvider
from app.providers.hotel import hotel_provider
from app.providers.rail import DatasetRailProvider, MockRailProvider
from app.schemas.product import HotelCandidate, HotelQuery
from app.schemas.travel import (
    POI,
    DistanceQuery,
    DistanceResult,
    FlightOption,
    FlightQuery,
    POIQuery,
    RailOption,
    RailQuery,
    RouteOption,
    RouteQuery,
    ToolResult,
    WeatherQuery,
    WeatherRecord,
)


def create_server(settings: Settings | None = None) -> MCPServer:
    settings = settings or Settings()
    server = MCPServer("TripPilot Travel MCP", version="1.1.0", log_level="WARNING")

    async def invoke(name, query, source_mode, simulated_rain=False):
        live = source_mode == "live" and not settings.protocol_fixture
        if name == "search_flights":
            provider = (
                DatasetFlightProvider() if settings.flight_provider == "dataset" else RealFlightProvider()
            )
            state = provider.status
            external = False
        elif name == "search_rail":
            provider = DatasetRailProvider() if settings.rail_provider == "dataset" else MockRailProvider()
            state = "DATASET" if settings.rail_provider == "dataset" else "MOCK"
            external = False
        else:
            provider = (
                AmapProvider(
                    settings.amap_api_key.get_secret_value(),
                    timeout=settings.runtime_policy.tool_timeout_seconds,
                )
                if live and settings.amap_ready
                else MockAmapProvider(severe_rain=simulated_rain)
            )
            state = "PENDING" if isinstance(provider, AmapProvider) else "MOCK"
            external = isinstance(provider, AmapProvider)
        if name == "search_hotels":
            provider = hotel_provider(provider)
        runtime = RuntimeHarness(ExecutionBudget(policy=settings.runtime_policy))
        try:
            result = await runtime.invoke(
                lambda: getattr(provider, CONTRACTS[name][2])(query),
                component="Provider",
                timeout=settings.runtime_policy.tool_timeout_seconds,
                retries=0,
                external=external,
            )
            result = runtime.validate(CONTRACTS[name][1], result)
            state = getattr(provider, "status", state)
        except ControlledError as exc:
            result = ToolResult(status="error", error=exc.error)
            state = "FAILED"
        return {"result": result, "provider_state": state, "external_calls": int(external)}

    @server.tool()
    async def search_rail(
        query: RailQuery, source_mode: Literal["live", "fixture"] = "live"
    ) -> MCPReply[ToolResult[list[RailOption]]]:
        """Search existing railway datasets, including direct and transfer options."""
        return await invoke("search_rail", query, source_mode)

    @server.tool()
    async def search_poi(
        query: POIQuery, source_mode: Literal["live", "fixture"] = "live"
    ) -> MCPReply[ToolResult[list[POI]]]:
        """Find typed POIs through the existing Amap provider."""
        return await invoke("search_poi", query, source_mode)

    @server.tool()
    async def get_weather(
        query: WeatherQuery, source_mode: Literal["live", "fixture"] = "live", simulated_rain: bool = False
    ) -> MCPReply[ToolResult[list[WeatherRecord]]]:
        """Retrieve actual available forecasts without inventing missing dates."""
        return await invoke("get_weather", query, source_mode, simulated_rain and source_mode == "fixture")

    @server.tool()
    async def calculate_distance(
        query: DistanceQuery, source_mode: Literal["live", "fixture"] = "live"
    ) -> MCPReply[ToolResult[list[DistanceResult]]]:
        """Calculate distance through the existing provider."""
        return await invoke("calculate_distance", query, source_mode)

    @server.tool()
    async def plan_route(
        query: RouteQuery, source_mode: Literal["live", "fixture"] = "live"
    ) -> MCPReply[ToolResult[list[RouteOption]]]:
        """Plan local transit with typed route duration and provenance."""
        return await invoke("plan_route", query, source_mode)

    @server.tool()
    async def search_flights(
        query: FlightQuery, source_mode: Literal["live", "fixture"] = "live"
    ) -> MCPReply[ToolResult[list[FlightOption]]]:
        """Search clearly labelled flight datasets; no live inventory or booking."""
        return await invoke("search_flights", query, source_mode)

    @server.tool()
    async def search_hotels(
        query: HotelQuery, source_mode: Literal["live", "fixture"] = "live"
    ) -> MCPReply[ToolResult[list[HotelCandidate]]]:
        """Find hotel POIs through the existing Amap client; prices and availability unknown."""
        return await invoke("search_hotels", query, source_mode)

    return server


def create_app():
    configure_logging()
    return create_server().streamable_http_app(stateless_http=True, json_response=True)
