import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

from app.core.errors import ControlledError
from app.providers.fixtures import FIXED_NOW, STATIONS, TZ
from app.schemas.travel import Evidence, RailLeg, RailOption, RailQuery, ToolResult


class RailProvider(Protocol):
    async def search(self, query: RailQuery) -> ToolResult[list[RailOption]]: ...


class MockRailProvider:
    def __init__(self, disruption: bool = False) -> None:
        self.disruption = disruption

    async def search(self, query: RailQuery) -> ToolResult[list[RailOption]]:
        if (
            query.origin not in STATIONS
            or query.destination not in STATIONS
            or query.origin == query.destination
        ):
            return ToolResult(status="empty", data=[])
        pairs = {
            frozenset(["上海", "杭州"]): (60, 7300),
            frozenset(["上海", "苏州"]): (35, 4000),
            frozenset(["上海", "南京"]): (100, 14000),
            frozenset(["杭州", "南京"]): (100, 11700),
            frozenset(["杭州", "苏州"]): (90, 11000),
            frozenset(["苏州", "南京"]): (80, 10000),
        }
        duration, price = pairs.get(frozenset([query.origin, query.destination]), (270, 55000))
        eid = f"rail-{query.origin}-{query.destination}-{query.date}"
        evidence = Evidence(
            id=eid,
            provider="MockRailProvider",
            source_kind="mock",
            retrieved_at=FIXED_NOW,
            valid_for=[query.date],
            notes="合成时刻和票价，仅供演示；不代表实际车次或余票。",
        )
        options = []
        for index, hour in enumerate([10, 12]):
            departure = datetime.combine(query.date, datetime.min.time(), TZ).replace(hour=hour, minute=20)
            leg = RailLeg(
                train_no=f"DEMO-G{list(STATIONS).index(query.origin) + 1}{list(STATIONS).index(query.destination) + 1}{index}",
                origin_station=STATIONS[query.origin],
                destination_station=STATIONS[query.destination],
                departure_time=departure,
                arrival_time=departure + timedelta(minutes=duration),
                duration=duration,
                price=price,
                evidence_id=eid,
                availability="unavailable" if self.disruption and index == 0 else "unknown",
            )
            options.append(RailOption(id=f"{eid}-{index}", legs=[leg]))
        return ToolResult(data=options, evidence=[evidence])


class DatasetRailProvider:
    def __init__(self, path: Path | None = None) -> None:
        self.additional = path is None
        self.path = path or Path(__file__).parent / "data" / "rail.json"

    async def search(self, query: RailQuery) -> ToolResult[list[RailOption]]:
        try:
            rows = json.loads(self.path.read_text())["options"]
            if self.additional:
                rows += json.loads((Path(__file__).parent / "data" / "rail_v12.json").read_text())["options"]
            records = [RailOption.model_validate(r) for r in rows]
        except (OSError, ValueError, KeyError):
            raise ControlledError("INVALID_OUTPUT") from None
        matches = [
            r
            for r in records
            if r.legs[0].origin_station.city == query.origin
            and r.legs[-1].destination_station.city == query.destination
            and r.legs[0].departure_time.date() == query.date
            and (query.allow_transfer or r.direct)
        ]
        evidence = [
            Evidence(
                id=leg.evidence_id,
                provider="DatasetRailProvider",
                source_kind="dataset",
                retrieved_at=FIXED_NOW,
                valid_for=[query.date],
                notes="版本化合成数据集；余票未知。",
            )
            for r in matches
            for leg in r.legs
        ]
        return ToolResult(status="ok" if matches else "empty", data=matches[:10], evidence=evidence)


class RealRailProvider:
    async def search(self, query: RailQuery) -> ToolResult[list[RailOption]]:
        return ToolResult(status="unavailable", error=ControlledError("UNSUPPORTED").error)
