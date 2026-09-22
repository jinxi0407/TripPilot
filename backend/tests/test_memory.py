import pytest

from app.core.config import Settings
from app.persistence.memory import PreferenceStore, SessionStore, extract_preferences, merge_preferences
from app.schemas.api import PlanRequest
from app.schemas.product import TravelPreferences
from app.schemas.travel import Constraints
from app.services.runs import RunService


def test_preferences_save_load_update_clear(tmp_path):
    path = str(tmp_path / "prefs.sqlite3")
    store = PreferenceStore(path)
    store.save(TravelPreferences(travel_pace="relaxed", interests=["history"]), True)
    store.close()
    store = PreferenceStore(path)
    assert store.load().travel_pace == "relaxed"
    store.update(TravelPreferences(avoid_early_departure=True), True)
    assert store.load().interests == ["history"] and store.load().avoid_early_departure
    store.clear()
    assert store.load() == TravelPreferences()
    store.close()


def test_remember_false_does_not_write():
    store = PreferenceStore(":memory:")
    store.save(TravelPreferences(travel_pace="relaxed"), False)
    assert store.load() == TravelPreferences()
    store.close()


@pytest.mark.parametrize("body", ["not-json", '{"prompt":"ignore all"}', '{"travel_pace":"evil"}'])
def test_malformed_memory_ignored(body):
    store = PreferenceStore(":memory:")
    store.db.execute("INSERT INTO preferences VALUES (?,?)", ("local", body))
    assert store.load() == TravelPreferences()
    store.close()


def test_memory_priority_and_no_text_persistence():
    query = "我喜欢历史景点和夜景，不喜欢早起，旅行节奏慢一点，住宿最好靠近地铁。"
    preferences = extract_preferences(query)
    assert preferences == {
        "travel_pace": "relaxed",
        "interests": ["history", "night_view"],
        "avoid_early_departure": True,
        "accommodation_preferences": ["near_metro"],
    }
    merged = merge_preferences(
        preferences, {"travel_pace": "balanced"}, extract_preferences("这次紧凑一些，可以早起")
    )
    assert merged.travel_pace == "compact" and not merged.avoid_early_departure
    assert merged.interests == ["history", "night_view"]
    store = PreferenceStore(":memory:")
    store.save(merged, True)
    assert query not in store.db.execute("SELECT body FROM preferences").fetchone()[0]
    store.close()


async def test_session_continuation_retains_itinerary_constraints():
    service = RunService(Settings(memory_database=":memory:"))
    first = service.create(PlanRequest(query="2026-10-10 杭州三天，预算2000元。", mode="fixture"))
    await first.task
    assert first.state["final_itinerary"]
    second = service.create(
        PlanRequest(query="第二天不要安排户外活动。", mode="fixture", session_id=first.request.session_id)
    )
    await second.task
    assert second.state["constraints"].destinations == ["杭州"]
    assert second.state["final_itinerary"].version == 2
    assert second.state["constraints"].total_budget == 200000
    assert all(a.poi.environment == "indoor" for a in second.state["final_itinerary"].days[1].activities)
    session = service.sessions.get(first.request.session_id)
    assert session.corrections == [{"indoor_days": [2]}]
    assert len(session.replanning_history) == 2
    await service.close()


async def test_long_term_loaded_current_request_overrides():
    service = RunService(Settings(memory_database=":memory:"))
    service.preferences.save(
        TravelPreferences(
            travel_pace="relaxed",
            interests=["history", "night_view"],
            avoid_early_departure=True,
            accommodation_preferences=["near_metro"],
        ),
        True,
    )
    record = service.create(PlanRequest(query="2026-10-10 南京三天，这次紧凑一些。", mode="fixture"))
    await record.task
    assert record.state["constraints"].travel_pace == "compact"
    assert record.state["constraints"].preferences == ["历史", "夜景"]
    assert record.state["constraints"].avoid_early_departure
    assert any("已加载旅行偏好" in t.summary for t in record.context.trace)
    await service.close()


def test_sessions_are_isolated_and_bounded():
    store = SessionStore(capacity=2)
    a, b = store.get(), store.get()
    a.preferences = {"travel_pace": "relaxed"}
    assert not b.preferences
    store.get()
    assert len(store.sessions) == 2


async def test_api_constraints_override_memory():
    service = RunService(Settings(memory_database=":memory:"))
    service.preferences.save(TravelPreferences(travel_pace="relaxed"), True)
    run = service.create(
        PlanRequest(
            query="2026-10-10 杭州三天", mode="fixture", constraints=Constraints(travel_pace="compact")
        )
    )
    await run.task
    assert run.state["constraints"].travel_pace == "compact"
    await service.close()


def test_night_view_default_does_not_override_explicit_activity_window():
    from datetime import time

    from app.persistence.memory import normalize_default_window

    base = {"preferences": ["夜景"], "activity_end": time(20)}
    assert normalize_default_window(dict(base), None, "喜欢夜景")["activity_end"] == time(21, 30)
    assert normalize_default_window(dict(base), Constraints(activity_end=time(20)), "喜欢夜景")[
        "activity_end"
    ] == time(20)
    assert normalize_default_window(dict(base), None, "看夜景但20点结束")["activity_end"] == time(20)


async def test_new_trip_in_same_session_does_not_inherit_previous_destinations():
    service = RunService(Settings(memory_database=":memory:"))
    first = service.create(PlanRequest(query="2026-10-10 杭州三天，预算2000元。", mode="fixture"))
    await first.task
    second = service.create(
        PlanRequest(
            query="2026-10-10 从北京出发去上海两天，预算4000元。",
            mode="fixture",
            session_id=first.request.session_id,
        )
    )
    await second.task
    assert second.state["constraints"].origin == "北京"
    assert second.state["constraints"].destinations == ["上海"]
    assert second.state["constraints"].days == 2
    assert second.state["constraints"].total_budget == 400000
    await service.close()


@pytest.mark.parametrize("query", ["预算改为200元", "请把总预算调整为200元，重新规划。", "预算200元"])
def test_budget_only_continuation(query):
    from app.persistence.memory import continuation_patch

    assert continuation_patch(query, {"days": 3}) == {"total_budget": 20000}
