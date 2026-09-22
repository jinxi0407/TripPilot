import hashlib
from collections import Counter
from pathlib import Path
from typing import Literal

from app.schemas.api import PlanRequest
from app.schemas.product import TravelPreferences
from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = Path(__file__).parent


class BenchmarkCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    category: Literal["A", "B", "C", "D", "E"]
    query: str
    turns: list[str] = Field(default_factory=list)
    request: PlanRequest
    stored_preferences: TravelPreferences | None = None
    scenario: Literal["normal", "rain"] = "normal"
    required_destinations: list[str]
    hard_constraints: dict
    soft_preferences: dict
    expected_agent_routes: list[str]
    required_tools: list[str]
    forbidden_tools: list[str] = Field(
        default_factory=lambda: ["delete_database", "purchase_ticket"]
    )
    requires_replanning: bool = False
    requires_memory: bool = False
    requires_hotel: bool = False
    requires_transport_comparison: bool = False
    budget_limit: int | None = None
    expected_failure_allowed: bool = False
    notes: str


def load_cases(path=None):
    path = path or DIRECTORY / "benchmark_50.jsonl"
    cases = [
        BenchmarkCase.model_validate_json(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]
    assert len(cases) == len({c.id for c in cases}) == 50
    assert Counter(c.category for c in cases) == dict.fromkeys("ABCDE", 10)
    for c in cases:
        assert c.query == c.request.query and c.required_destinations
        assert c.request.mode == "live"
        assert set(c.required_tools) <= {
            "search_rail",
            "search_flights",
            "search_poi",
            "search_hotels",
            "get_weather",
            "calculate_distance",
            "plan_route",
        }
        assert c.notes and c.hard_constraints
    return cases


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
