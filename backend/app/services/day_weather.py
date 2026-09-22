"""A presentation projection of existing tool evidence; never asks a model for weather."""

from datetime import date

from app.graph.state import AgentState
from app.schemas.travel import DayWeather


def day_weather(state: AgentState, city: str, day: date) -> DayWeather:
    pending = DayWeather(city=city, forecast_date=day)
    record = next((w for w in state.get("weather_data", []) if w.city == city and w.date == day), None)
    if not record:
        return pending
    evidence = state.get("evidence", {}).get(record.evidence_id)
    if not evidence or evidence.stale or day not in evidence.valid_for or record.severity == "unknown":
        return pending
    if evidence.source != "amap_live" or evidence.source_kind != "live":
        return DayWeather(
            city=city,
            forecast_date=day,
            source=evidence.source or evidence.provider,
            status="simulated",
            weather_condition=record.condition,
            evidence_id=record.evidence_id,
        )
    return DayWeather(
        city=city,
        forecast_date=day,
        source="amap_live",
        status="live",
        weather_condition=record.condition,
        min_temperature=record.min_temperature,
        max_temperature=record.max_temperature,
        precipitation=record.precipitation,
        precipitation_probability=record.precipitation_probability,
        evidence_id=record.evidence_id,
    )
