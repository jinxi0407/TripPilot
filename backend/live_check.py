"""Explicit, opt-in live checks. Prints/writes only allowlisted public business results."""

import argparse
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import BaseModel

from app.core.budget import ExecutionBudget
from app.core.config import Settings
from app.core.errors import ControlledError
from app.core.logging import configure_logging
from app.providers.amap import AmapProvider
from app.providers.fixtures import TZ
from app.schemas.travel import DistanceQuery, Place, POIQuery, RouteQuery, WeatherQuery
from app.services.model_client import QwenClient, structured_call


class Ping(BaseModel):
    ok: bool


async def run_checks() -> dict:
    configure_logging()
    settings = Settings()
    report = {"checked_at": datetime.now(TZ).isoformat(), "rail": settings.rail_provider or "mock"}
    if settings.model_ready:
        model = QwenClient(settings)
        try:
            result = await structured_call(
                model, {"instruction": '仅返回 JSON: {"ok":true}'}, Ping, ExecutionBudget(), []
            )
            report["qwen"] = {
                "status": model.status,
                "model": model.actual_model,
                "structured_output": result.ok,
            }
        except ControlledError as exc:
            report["qwen"] = {"status": "FAILED", "error": exc.error.model_dump()}
    else:
        report["qwen"] = {"status": "UNCONFIGURED", "model_configured": bool(settings.qwen_model)}
    provider = AmapProvider(settings.amap_api_key.get_secret_value())
    results = {}
    pois = []
    for name, keywords in [("west_lake", "西湖"), ("lingyin", "西湖区灵隐寺")]:
        try:
            result = await provider.pois(POIQuery(city="杭州", keywords=keywords, limit=3))
            poi = result.data[0] if result.data else None
            results[name] = {
                "status": result.status,
                "source": "amap_live",
                "poi": poi.model_dump(mode="json") if poi else None,
            }
            if poi:
                pois.append(poi)
        except ControlledError as exc:
            results[name] = {"status": "FAILED", "error": exc.error.model_dump()}
    today = datetime.now(TZ).date()
    queries = [
        (
            "weather",
            provider.weather,
            WeatherQuery(city="杭州", dates=[today + timedelta(days=i) for i in range(4)]),
        )
    ]
    if len(pois) == 2:
        origin, destination = [
            Place.model_validate(p.model_dump(include={"id", "name", "city", "coordinates"})) for p in pois
        ]
        queries.extend(
            [
                (
                    "distance",
                    provider.distance,
                    DistanceQuery(
                        origin=origin.coordinates, destination=destination.coordinates, mode="drive"
                    ),
                ),
                ("route", provider.route, RouteQuery(origin=origin, destination=destination, mode="transit")),
            ]
        )
    for name, handler, query in queries:
        try:
            result = await handler(query)
            results[name] = result.model_dump(mode="json")
        except ControlledError as exc:
            results[name] = {"status": "FAILED", "error": exc.error.model_dump()}
    report["amap"] = results
    report["map_configuration"] = {
        "js_key": "configured" if settings.vite_amap_js_key.get_secret_value() else "missing",
        "security_code": "configured" if settings.vite_amap_security_code.get_secret_value() else "missing",
    }
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-live", action="store_true", required=True)
    args = parser.parse_args()
    try:
        report = asyncio.run(run_checks())
        output = Path(__file__).resolve().parents[1] / "docs" / "live-api-check.json"
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(
            json.dumps(
                {
                    "qwen": report["qwen"],
                    "amap": {k: v["status"] for k, v in report["amap"].items()},
                    "map_configuration": report["map_configuration"],
                },
                ensure_ascii=False,
            )
        )
    except Exception:  # noqa: BLE001 - never print upstream exceptions with credential-bearing URLs
        print("LIVE_CHECK_FAILED: unexpected sanitized failure")
        raise SystemExit(1) from None
