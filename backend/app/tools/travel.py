from app.core.budget import ExecutionBudget
from app.providers.amap import LocalProvider
from app.providers.rail import RailProvider
from app.schemas.travel import (
    POI,
    DistanceQuery,
    DistanceResult,
    POIQuery,
    RailOption,
    RailQuery,
    RouteOption,
    RouteQuery,
    ToolResult,
    WeatherQuery,
    WeatherRecord,
)
from app.tools.registry import Tool, ToolRegistry

LOCAL_AGENTS = frozenset({"Local Travel", "Travel Planner"})


class AmapPOITool(Tool):
    def __init__(self, provider: LocalProvider) -> None:
        super().__init__("amap_poi", POIQuery, ToolResult[list[POI]], provider.pois, LOCAL_AGENTS)


class AmapRouteTool(Tool):
    def __init__(self, provider: LocalProvider) -> None:
        super().__init__(
            "amap_route", RouteQuery, ToolResult[list[RouteOption]], provider.route, LOCAL_AGENTS
        )


class AmapDistanceTool(Tool):
    def __init__(self, provider: LocalProvider) -> None:
        super().__init__(
            "amap_distance", DistanceQuery, ToolResult[list[DistanceResult]], provider.distance, LOCAL_AGENTS
        )


class AmapWeatherTool(Tool):
    def __init__(self, provider: LocalProvider) -> None:
        super().__init__(
            "amap_weather", WeatherQuery, ToolResult[list[WeatherRecord]], provider.weather, LOCAL_AGENTS
        )


def create_registry(rail: RailProvider, local: LocalProvider, budget: ExecutionBudget) -> ToolRegistry:
    return ToolRegistry(
        [
            Tool(
                "rail_search",
                RailQuery,
                ToolResult[list[RailOption]],
                rail.search,
                frozenset({"Transport", "Travel Planner"}),
            ),
            AmapPOITool(local),
            AmapRouteTool(local),
            AmapDistanceTool(local),
            AmapWeatherTool(local),
        ],
        budget,
    )
