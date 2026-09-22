import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evals.compare import frozen_evidence
from evals.runner import load_cases, run_case


@pytest.mark.parametrize("case", load_cases(), ids=lambda c: c.id)
async def test_evaluation_case(case):
    row = await run_case(case)
    # Historical labels remain immutable; assert the current schema translation.
    aliases = {
        "OPENING_TIME_CONFLICT": "OPENING_HOURS_CONFLICT",
        "TRAIN_DEPARTURE_RISK": "TRANSPORT_CONFLICT",
        "TRANSFER_RISK": "TRANSPORT_CONFLICT",
        "BUDGET_UNKNOWN": "BUDGET_PARTIAL",
        "WEATHER_RISK": "WEATHER_CONFLICT",
        "WEATHER_UNKNOWN": "WEATHER_UNAVAILABLE",
    }
    expected = case.assertions["expected_issue"]
    checks = dict(row["checks"])
    if expected in aliases:
        assert aliases[expected] in row["issues_observed"]
        checks.pop("expected_issue")
    if case.fixture_overrides == "inefficient":
        # A soft optimization suggestion is no longer an automatic replan trigger.
        assert "ROUTE_INEFFICIENCY" in row["issues_observed"]
        checks.pop("issue_repaired")
    assert all(checks.values()), row
    assert row["metrics"]["token_usage"] is None


async def test_fixture_repeatability_and_frozen_evidence():
    case = load_cases()[0]
    a = await run_case(case)
    b = await run_case(case)
    assert a["metrics"] == b["metrics"] and a["checks"] == b["checks"]
    evidence = await frozen_evidence(case)
    assert evidence["route_data"] and all(e.source_kind == "mock" for e in evidence["evidence"].values())


async def test_baseline_one_call_and_same_validator(monkeypatch):
    from evals import compare

    from app.core.config import Settings
    from app.services.itinerary import default_selections
    from app.services.model_client import MockModelClient

    case = load_cases()[0]
    state = await frozen_evidence(case)
    calls = []

    def respond(payload):
        calls.append(payload)
        return {"kind": "final", "selections": [s.model_dump() for s in default_selections(state)]}

    monkeypatch.setattr(compare, "QwenClient", lambda settings: MockModelClient(respond))
    result, context = await compare.baseline(case, Settings(_env_file=None), state)
    assert len(calls) == 1 and context.budget.models == 1
    assert result["validation_result"].valid
    assert result["final_itinerary"].costs.estimated_total > 0
