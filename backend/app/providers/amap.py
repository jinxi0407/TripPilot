import hashlib
import math
import re
from datetime import date, datetime
from typing import Any, Protocol

import httpx

from app.core.errors import ControlledError
from app.providers.fixtures import CITY_CODES, FIXED_NOW, TZ, city_pois
from app.schemas.travel import (
    POI,
    Coordinates,
    DistanceQuery,
    DistanceResult,
    Evidence,
    POIQuery,
    RouteOption,
    RouteQuery,
    ToolResult,
    WeatherQuery,
    WeatherRecord,
)


class LocalProvider(Protocol):
    async def pois(self, query: POIQuery) -> ToolResult[list[POI]]: ...
    async def route(self, query: RouteQuery) -> ToolResult[list[RouteOption]]: ...
    async def distance(self, query: DistanceQuery) -> ToolResult[list[DistanceResult]]: ...
    async def weather(self, query: WeatherQuery) -> ToolResult[list[WeatherRecord]]: ...


def straight_distance(a: Coordinates, b: Coordinates) -> int:
    lat1, lat2 = math.radians(a.latitude), math.radians(b.latitude)
    dlat, dlon = lat2 - lat1, math.radians(b.longitude - a.longitude)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return round(6371000 * 2 * math.asin(min(1, math.sqrt(h))))


def route_id(query: RouteQuery) -> str:
    return f"{query.origin.id}:{query.destination.id}:{query.mode}"


class MockAmapProvider:
    def __init__(self, severe_rain: bool = False, outage: bool = False) -> None:
        self.severe_rain = severe_rain
        self.outage = outage

    def evidence(self, eid: str, dates: list[date] | None = None) -> Evidence:
        return Evidence(
            id=eid,
            provider="MockAmapProvider",
            source_kind="mock",
            retrieved_at=FIXED_NOW,
            valid_for=dates or [],
            notes="合成演示数据，非实时高德结果。",
        )

    async def pois(self, query: POIQuery) -> ToolResult[list[POI]]:
        if self.outage:
            raise ControlledError("TIMEOUT", retryable=True)
        data = city_pois(query.city)
        if query.category == "restaurant" and data:
            data = [
                POI(
                    id=f"food-{query.city}",
                    name=f"{query.city}本地菜馆（演示）",
                    city=query.city,
                    category="restaurant",
                    environment="indoor",
                    coordinates=data[0].coordinates,
                    evidence_id=f"poi-{query.city}",
                )
            ]
        if query.keywords:
            data = [p for p in data if query.keywords in p.name or query.keywords in p.tags]
        return ToolResult(
            status="ok" if data else "empty",
            data=data[: query.limit],
            evidence=[self.evidence(f"poi-{query.city}")],
        )

    async def route(self, query: RouteQuery) -> ToolResult[list[RouteOption]]:
        if not query.origin.coordinates or not query.destination.coordinates:
            raise ControlledError("UNSUPPORTED")
        meters = round(straight_distance(query.origin.coordinates, query.destination.coordinates) * 1.35)
        # Synthetic route estimates are identified as mock and are not live road calculations.
        duration = max(
            8,
            math.ceil(meters / {"walk": 70, "drive": 500, "transit": 380}[query.mode])
            + (10 if query.mode == "transit" else 0),
        )
        eid = "route-" + route_id(query)
        return ToolResult(
            data=[
                RouteOption(
                    id=route_id(query),
                    origin=query.origin,
                    destination=query.destination,
                    mode=query.mode,
                    duration=duration,
                    distance=meters,
                    price=0 if query.mode == "walk" else (400 if query.mode == "transit" else 3000),
                    evidence_id=eid,
                )
            ],
            evidence=[self.evidence(eid)],
        )

    async def distance(self, query: DistanceQuery) -> ToolResult[list[DistanceResult]]:
        eid = "distance-" + hashlib.sha256(query.model_dump_json().encode()).hexdigest()[:10]
        meters = straight_distance(query.origin, query.destination)
        if query.mode != "straight":
            meters = round(meters * 1.35)
        return ToolResult(
            data=[DistanceResult(meters=meters, methodology=query.mode, evidence_id=eid)],
            evidence=[self.evidence(eid)],
        )

    async def weather(self, query: WeatherQuery) -> ToolResult[list[WeatherRecord]]:
        eid = f"weather-{query.city}-{self.severe_rain}"
        dates = [d for d in query.dates if date(2026, 10, 10) <= d <= date(2026, 10, 16)]
        if not dates:
            return ToolResult(status="unavailable", error=ControlledError("UNSUPPORTED").error)
        return ToolResult(
            data=[
                WeatherRecord(
                    city=query.city,
                    date=d,
                    condition="暴雨（模拟）" if self.severe_rain else "晴间多云（模拟）",
                    severity="severe" if self.severe_rain else "normal",
                    temperature="18–25°C",
                    evidence_id=eid,
                )
                for d in dates
            ],
            evidence=[self.evidence(eid, dates)],
        )


class AmapProvider:
    def __init__(self, key: str, transport: httpx.AsyncBaseTransport | None = None, timeout: float = 10) -> None:
        self._key = key
        self.transport = transport
        self.timeout = timeout
        self.status = "PENDING" if key else "UNCONFIGURED"
        self.error_code: str | None = None

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            result = await self._request(path, params)
        except ControlledError as exc:
            self.status = "FAILED"
            self.error_code = exc.error.provider_code or exc.error.code
            raise
        self.status = "LIVE"
        self.error_code = None
        return result

    async def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self._key:
            raise ControlledError("AUTH_REQUIRED")
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                response = await client.get(
                    "https://restapi.amap.com/v3/" + path, params={**params, "key": self._key}
                )
            if response.status_code == 429:
                raise ControlledError("RATE_LIMITED", retryable=True)
            if response.status_code >= 400:
                raise ControlledError("PROVIDER_FAILURE", retryable=response.status_code >= 500)
            data = response.json()
            if data.get("status") != "1":
                code = str(data.get("infocode", ""))
                if code in ("10001", "10002", "10005", "10006", "10007", "10008", "10009", "10012", "10013"):
                    raise ControlledError("AUTH_REQUIRED", provider_code=code)
                if code in ("10003", "10004", "10010", "10014", "10019", "10020", "10021", "10029"):
                    raise ControlledError("RATE_LIMITED", retryable=code == "10004", provider_code=code)
                raise ControlledError("PROVIDER_FAILURE", provider_code=code)
            return data
        except httpx.TimeoutException:
            raise ControlledError("TIMEOUT", retryable=True) from None
        except httpx.RequestError:
            raise ControlledError("PROVIDER_FAILURE", retryable=True) from None
        except (ValueError, TypeError):
            raise ControlledError("INVALID_OUTPUT") from None

    def evidence(self, eid: str, dates: list[date] | None = None) -> Evidence:
        return Evidence(
            id=eid,
            provider="AmapProvider",
            source_kind="live",
            source="amap_live",
            retrieved_at=datetime.now(TZ),
            valid_for=dates or [],
            notes="高德 Web Service API",
        )

    @staticmethod
    def coords(value: str) -> Coordinates:
        lon, lat = value.split(",")
        return Coordinates(longitude=float(lon), latitude=float(lat))

    async def pois(self, query: POIQuery) -> ToolResult[list[POI]]:
        data = await self._get(
            "place/text",
            {
                "city": query.city,
                "citylimit": "true",
                "keywords": query.keywords,
                "types": "050000" if query.category == "restaurant" else "110000|140000",
                "offset": 20 if query.keywords else query.limit,
                "page": 1,
                "extensions": "all",
            },
        )
        eid = f"poi-{query.city}-{query.category}-" + hashlib.sha256(query.keywords.encode()).hexdigest()[:8]
        try:
            rows = data["pois"]
            if query.keywords:

                def relevance(row):
                    name = row["name"]
                    base_name = re.sub(r"[（(].*?[）)]", "", name)
                    # Prefer the named attraction over its sub-POIs; otherwise
                    # preserve Amap's relevance order rather than shortest name.
                    return 0 if base_name == query.keywords else 1

                rows = sorted(rows, key=relevance)
            pois = [
                POI(
                    id=str(row["id"]),
                    name=row["name"],
                    city=query.city,
                    category=query.category,
                    coordinates=self.coords(row["location"]) if row.get("location") else None,
                    evidence_id=eid,
                    environment="indoor"
                    if any(t in row["name"] for t in ("博物馆", "博物院", "美术馆"))
                    else "unknown",
                )
                for row in rows[: query.limit]
            ]
        except (ValueError, KeyError, TypeError):
            raise ControlledError("INVALID_OUTPUT") from None
        return ToolResult(status="ok" if pois else "empty", data=pois, evidence=[self.evidence(eid)])

    @staticmethod
    def point(c: Coordinates | None) -> str:
        if c is None:
            raise ControlledError("UNSUPPORTED")
        return f"{c.longitude},{c.latitude}"

    async def route(self, query: RouteQuery) -> ToolResult[list[RouteOption]]:
        params = {
            "origin": self.point(query.origin.coordinates),
            "destination": self.point(query.destination.coordinates),
        }
        paths = {
            "walk": "direction/walking",
            "drive": "direction/driving",
            "transit": "direction/transit/integrated",
        }
        if query.mode == "transit":
            params.update(city=query.origin.city, cityd=query.destination.city)
        data = await self._get(paths[query.mode], params)
        eid = "route-" + route_id(query)
        try:
            entries = data["route"].get("transits" if query.mode == "transit" else "paths", [])
            rows = [
                RouteOption(
                    id=route_id(query),
                    origin=query.origin,
                    destination=query.destination,
                    mode=query.mode,
                    duration=max(1, math.ceil(float(r["duration"]) / 60)),
                    distance=int(r["distance"]),
                    price=round(float(r["cost"]) * 100)
                    if query.mode == "transit" and r.get("cost") not in (None, "", [])
                    else (0 if query.mode == "walk" else None),
                    evidence_id=eid,
                )
                for r in entries[:1]
            ]
        except (KeyError, TypeError, ValueError):
            raise ControlledError("INVALID_OUTPUT") from None
        return ToolResult(status="ok" if rows else "unavailable", data=rows, evidence=[self.evidence(eid)])

    async def distance(self, query: DistanceQuery) -> ToolResult[list[DistanceResult]]:
        data = await self._get(
            "distance",
            {
                "origins": self.point(query.origin),
                "destination": self.point(query.destination),
                "type": {"straight": 0, "drive": 1, "walk": 3}[query.mode],
            },
        )
        eid = "distance-" + hashlib.sha256(query.model_dump_json().encode()).hexdigest()[:10]
        try:
            rows = [
                DistanceResult(meters=int(r["distance"]), methodology=query.mode, evidence_id=eid)
                for r in data["results"]
                if str(r.get("info", "1")) == "1"
            ]
        except (KeyError, TypeError, ValueError):
            raise ControlledError("INVALID_OUTPUT") from None
        return ToolResult(status="ok" if rows else "unavailable", data=rows, evidence=[self.evidence(eid)])

    async def weather(self, query: WeatherQuery) -> ToolResult[list[WeatherRecord]]:
        code = CITY_CODES.get(query.city)
        if code is None:
            raise ControlledError("UNSUPPORTED")
        data = await self._get("weather/weatherInfo", {"city": code, "extensions": "all"})
        eid = f"weather-{query.city}"
        try:
            rows = []
            for forecast in data["forecasts"]:
                for cast in forecast["casts"]:
                    day = date.fromisoformat(cast["date"])
                    if day in query.dates:
                        condition = cast["dayweather"]
                        severity = (
                            "severe"
                            if any(s in condition for s in ("暴雨", "雷", "暴雪", "台风"))
                            else ("adverse" if "雨" in condition or "雪" in condition else "normal")
                        )
                        rows.append(
                            WeatherRecord(
                                city=query.city,
                                date=day,
                                condition=condition,
                                severity=severity,
                                temperature=str(cast.get("daytemp", "")),
                                evidence_id=eid,
                            )
                        )
        except (KeyError, TypeError, ValueError):
            raise ControlledError("INVALID_OUTPUT") from None
        return ToolResult(
            status="ok" if rows else "unavailable",
            data=rows,
            evidence=[self.evidence(eid, [r.date for r in rows])],
        )
