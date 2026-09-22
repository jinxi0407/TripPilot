import json
from pathlib import Path
from typing import Protocol

from app.core.errors import ControlledError
from app.providers.fixtures import FIXED_NOW
from app.schemas.travel import Evidence, FlightOption, FlightQuery, ToolResult


class FlightProvider(Protocol):
    async def search(self, query: FlightQuery) -> ToolResult[list[FlightOption]]: ...


class DatasetFlightProvider:
    status = "DATASET"

    def __init__(self, path: Path | None = None):
        self.path = path or Path(__file__).parent / "data" / "flights.json"

    async def search(self, query: FlightQuery) -> ToolResult[list[FlightOption]]:
        try:
            records = [FlightOption.model_validate(r) for r in json.loads(self.path.read_text())["options"]]
        except (OSError, ValueError, KeyError):
            raise ControlledError("INVALID_OUTPUT") from None
        matches = [
            r
            for r in records
            if r.origin_airport.city == query.origin
            and r.destination_airport.city == query.destination
            and r.departure_time.date() == query.date
        ]
        evidence = [
            Evidence(
                id=r.evidence_id,
                provider="DatasetFlightProvider",
                source_kind="dataset",
                source="flight_dataset_v1",
                retrieved_at=FIXED_NOW,
                valid_for=[query.date],
                notes="固定合成航班与演示价格；无实时库存，不可用于订票。",
            )
            for r in matches
        ]
        return ToolResult(status="ok" if matches else "empty", data=matches, evidence=evidence)


class RealFlightProvider:
    status = "UNCONFIGURED"

    async def search(self, query: FlightQuery) -> ToolResult[list[FlightOption]]:
        return ToolResult(status="unavailable", error=ControlledError("UNSUPPORTED").error)
