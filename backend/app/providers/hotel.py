import hashlib
from typing import Protocol

from app.core.errors import ControlledError
from app.providers.amap import AmapProvider, MockAmapProvider, straight_distance
from app.providers.fixtures import city_pois
from app.schemas.product import HotelCandidate, HotelQuery
from app.schemas.travel import Coordinates, ToolResult


class HotelProvider(Protocol):
    async def search(self, query: HotelQuery) -> ToolResult[list[HotelCandidate]]: ...


class AmapHotelProvider:
    def __init__(self, local: AmapProvider):
        self.local = local

    @property
    def status(self):
        return self.local.status

    async def search(self, query: HotelQuery) -> ToolResult[list[HotelCandidate]]:
        params = {
            "city": query.city,
            "citylimit": "true",
            "keywords": query.keywords,
            "types": "100000",
            "offset": query.limit,
            "page": 1,
            "extensions": "base",
        }
        path = "place/text"
        if query.center:
            path = "place/around"
            params.update(location=self.local.point(query.center), radius=5000, sortrule="distance")
        data = await self.local._get(path, params)
        eid = "hotel-" + hashlib.sha256(query.model_dump_json().encode()).hexdigest()[:12]
        candidates = []
        try:
            for row in data["pois"][: query.limit]:
                if not row.get("id") or not row.get("name"):
                    continue

                def optional_text(key, row=row):
                    return row[key] if isinstance(row.get(key), str) and row[key] else None

                coordinates = self.local.coords(row["location"]) if row.get("location") else None
                distance = int(row["distance"]) if str(row.get("distance", "")).isdigit() else None
                candidates.append(
                    HotelCandidate(
                        id=str(row["id"]),
                        name=row["name"],
                        hotel_name=row["name"],
                        city=query.city,
                        coordinates=coordinates,
                        address=optional_text("address"),
                        district=optional_text("adname"),
                        source="amap_live",
                        evidence_id=eid,
                        distance_meters=distance,
                        distance_kind="provider" if distance is not None else "unknown",
                    )
                )
        except (KeyError, ValueError, TypeError):
            raise ControlledError("INVALID_OUTPUT") from None
        return ToolResult(
            status="ok" if candidates else "empty", data=candidates, evidence=[self.local.evidence(eid)]
        )


class FixtureHotelProvider:
    def __init__(self, local: MockAmapProvider):
        self.local = local
        self.status = "MOCK"

    async def search(self, query: HotelQuery) -> ToolResult[list[HotelCandidate]]:
        if self.local.outage:
            raise ControlledError("TIMEOUT", retryable=True)
        pois = city_pois(query.city)
        if not pois:
            return ToolResult(status="empty", data=[])
        center = query.center or pois[0].coordinates
        eid = "hotel-fixture-" + query.city
        hotels = []
        for n, offset in enumerate([0.003, 0.012, 0.035][: query.limit]):
            c = Coordinates(longitude=center.longitude + offset, latitude=center.latitude + offset / 2)
            hotels.append(
                HotelCandidate(
                    id=f"hotel-{query.city}-{n}",
                    name=f"{query.city}演示酒店{n + 1}",
                    hotel_name=f"{query.city}演示酒店{n + 1}",
                    city=query.city,
                    coordinates=c,
                    address=f"合成住宿街区 {n + 1} 号",
                    district="演示中心城区",
                    source="hotel_fixture",
                    evidence_id=eid,
                    distance_meters=straight_distance(center, c),
                    distance_kind="estimated_straight",
                )
            )
        return ToolResult(data=hotels, evidence=[self.local.evidence(eid)])


def hotel_provider(local):
    return AmapHotelProvider(local) if isinstance(local, AmapProvider) else FixtureHotelProvider(local)
