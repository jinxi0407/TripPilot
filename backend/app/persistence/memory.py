import re
import sqlite3
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from app.core.errors import ControlledError
from app.schemas.product import TravelPreferences


def extract_preferences(query: str) -> dict:
    """Explicit user preference phrases only; never persist the source text."""
    result = {}
    for words, field_name, value in [
        (("慢一点", "慢游", "轻松", "不太赶", "不想每天太赶"), "travel_pace", "relaxed"),
        (("紧凑", "密集"), "travel_pace", "compact"),
        (("不喜欢早起", "不要早班", "避免早班", "不早起"), "avoid_early_departure", True),
        (("可以早起", "可以早班"), "avoid_early_departure", False),
        (("偏好高铁", "喜欢高铁", "倾向高铁"), "transport_preference", "high_speed_rail"),
        (("偏好飞机", "喜欢飞机", "倾向飞机"), "transport_preference", "flight"),
        (("少走路", "步行少"), "walking_tolerance", "low"),
    ]:
        if any(word in query for word in words):
            result[field_name] = value
    interests = [
        v for k, v in [("历史", "history"), ("夜景", "night_view"), ("自然", "nature")] if k in query
    ]
    if interests:
        result["interests"] = interests
    accommodation = [
        v
        for k, v in [("地铁", "near_metro"), ("靠近景点", "close_to_main_pois"), ("靠近车站", "near_station")]
        if k in query
    ]
    if accommodation:
        result["accommodation_preferences"] = accommodation
    return result


class PreferenceStore:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS preferences (user_id TEXT PRIMARY KEY, body TEXT NOT NULL)"
        )
        self.db.commit()

    def load(self) -> TravelPreferences:
        row = self.db.execute("SELECT body FROM preferences WHERE user_id=?", ("local",)).fetchone()
        if not row:
            return TravelPreferences()
        try:
            return TravelPreferences.model_validate_json(row[0])
        except (ValidationError, ValueError):
            # Corrupt or older incompatible memory cannot become model instructions.
            return TravelPreferences()

    def save(self, preferences: TravelPreferences, remember: bool) -> TravelPreferences:
        validated = TravelPreferences.model_validate(preferences.model_dump())
        if remember:
            self.db.execute(
                "INSERT OR REPLACE INTO preferences VALUES (?,?)", ("local", validated.model_dump_json())
            )
            self.db.commit()
        return validated

    def update(self, preferences: TravelPreferences, remember: bool) -> TravelPreferences:
        data = self.load().model_dump()
        data.update(preferences.model_dump(exclude_unset=True))
        return self.save(TravelPreferences.model_validate(data), remember)

    def clear(self):
        self.db.execute("DELETE FROM preferences WHERE user_id=?", ("local",))
        self.db.commit()

    def close(self):
        self.db.close()


@dataclass
class SessionMemory:
    id: str = field(default_factory=lambda: str(uuid4()))
    constraints: dict = field(default_factory=dict)
    preferences: dict = field(default_factory=dict)
    current_itinerary: dict | None = None
    selected_transport: list = field(default_factory=list)
    accommodation_choices: list = field(default_factory=list)
    corrections: list[dict] = field(default_factory=list)
    replanning_history: list[dict] = field(default_factory=list)


class SessionStore:
    def __init__(self, capacity=50):
        self.sessions: OrderedDict[str, SessionMemory] = OrderedDict()
        self.capacity = capacity

    def get(self, session_id=None):
        if session_id is not None and session_id not in self.sessions:
            raise ControlledError("NOT_FOUND")
        session = self.sessions.get(session_id) if session_id else SessionMemory()
        self.sessions[session.id] = session
        self.sessions.move_to_end(session.id)
        while len(self.sessions) > self.capacity:
            self.sessions.popitem(last=False)
        return session


def continuation_patch(query: str, constraints: dict) -> dict:
    patch = {}
    day = re.search(r"第([一二三四五六七\d])天.*(?:不要.*户外|只.*室内|改.*室内)", query)
    if day:
        value = int(day[1]) if day[1].isdigit() else "一二三四五六七".index(day[1]) + 1
        if value > (constraints.get("days") or 0):
            raise ControlledError("INVALID_INPUT")
        patch["indoor_days"] = sorted(set(constraints.get("indoor_days", []) + [value]))
    money = re.fullmatch(
        r"\s*(?:请)?(?:把|将)?(?:总)?预算(?:改为|改成|调整为|为)?\s*(\d+)\s*元"
        r"[，,。！!\s]*(?:请)?(?:重新规划|重新安排)?[。！!\s]*",
        query,
    )
    if money:
        patch["total_budget"] = int(money[1]) * 100
    return patch


def merge_preferences(long_term: dict, session: dict, current: dict) -> TravelPreferences:
    return TravelPreferences.model_validate({**long_term, **session, **current})


def preference_constraints(preferences: TravelPreferences) -> dict:
    values = preferences.model_dump(exclude_none=True, exclude_unset=True)
    result = {k: v for k, v in values.items() if k not in {"interests", "budget_level"}}
    if values.get("interests"):
        result["preferences"] = [
            {"history": "历史", "night_view": "夜景", "nature": "自然"}[x] for x in values["interests"]
        ]
    if preferences.travel_pace:
        result["max_attractions"] = {"relaxed": 2, "balanced": 3, "compact": 4}[preferences.travel_pace]
    if preferences.walking_tolerance == "low":
        result["max_walk_minutes"] = 30
    return result


def normalize_default_window(data: dict, existing, query: str) -> dict:
    """Match fixture/live default night-view hours without overriding an explicit window."""
    from datetime import time

    fields = existing.model_fields_set if existing else set()
    explicit_time = bool(re.search(r"\d{1,2}点|\d{1,2}:\d{2}|晚上[一二三四五六七八九十]", query))
    if (
        "夜景" in data.get("preferences", [])
        and "activity_end" not in fields
        and not explicit_time
        and data.get("activity_end") in (None, time(20), "20:00:00")
    ):
        data["activity_end"] = time(21, 30)
    return data
