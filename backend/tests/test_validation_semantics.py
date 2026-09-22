from datetime import time, timedelta

import pytest
from evals.v1_2_2.evaluator import strict_replanning
from pydantic import ValidationError
from test_critic import demo

from app.agents.critic import critique, validate_itinerary
from app.schemas.travel import Issue, ValidationResult
from app.services.costing import reconcile
from app.services.itinerary import assemble, default_selections
from app.services.validation import finalize_validation


async def prepared():
    state, context = await demo()
    state["draft_itinerary"] = state["final_itinerary"].model_copy(deep=True)
    state["replanning_count"] = 0
    state["validation_history"] = []
    state["issue_signature"] = ""
    return state, context


def issue(state, kind):
    result = validate_itinerary(state["draft_itinerary"], state["constraints"], state)
    return next(i for i in result.issues if i.type == kind)


async def test_missing_opening_is_unverified_without_replan():
    state, context = await prepared()
    state["draft_itinerary"].days[0].activities[0].poi.opening_start = None
    i = issue(state, "OPENING_HOURS_UNVERIFIED")
    assert (i.status, i.severity, i.blocking) == ("unverified", "warning", False)
    assert i.activity_id and i.evidence["opening_start"] is None
    output = await critique(state, context)
    assert output["status"] == "partial" and "replanning_count" not in output


async def test_known_closed_is_confirmed_with_replan():
    state, context = await prepared()
    state["draft_itinerary"].days[0].activities[0].poi.opening_end = time(9)
    i = issue(state, "OPENING_HOURS_CONFLICT")
    assert (i.status, i.severity, i.blocking) == ("confirmed", "error", True)
    output = await critique(state, context)
    assert output["replanning_count"] == 1
    assert output["validation_history"][0]["replanning_requested"]


async def test_no_forecast_deduplicates_per_day_and_never_replans():
    state, context = await prepared()
    state["weather_data"] = []
    output = await critique(state, context)
    issues = [i for i in output["validation_result"].issues if i.type == "WEATHER_UNAVAILABLE"]
    assert len(issues) == 5 and all(not i.blocking for i in issues)
    assert output["status"] == "partial" and "replanning_count" not in output


async def test_stale_forecast_is_unverified():
    state, _ = await prepared()
    w = state["weather_data"][0]
    w.severity = "severe"
    state["evidence"][w.evidence_id].stale = True
    assert not issue(state, "WEATHER_UNAVAILABLE").blocking


async def test_severe_outdoor_replans_and_history_proves_resolution():
    state, _ = await demo("rain")
    assert state["validation_history"][0]["blocking"]
    assert strict_replanning(state, "trippilot") is True
    assert not state["validation_history"][-1]["blocking"]


async def test_missing_rail_is_uncertainty_not_infeasibility():
    state, _ = await prepared()
    state["draft_itinerary"].days[0].rail = None
    state["transport_options"] = state["transport_options"][1:]
    i = issue(state, "TRANSPORT_UNVERIFIED")
    assert not i.blocking and i.status == "unverified"


async def test_available_rail_maps_to_day_if_model_omits_id():
    state, _ = await prepared()
    selections = default_selections(state)
    for selection in selections:
        selection.rail_id = None
    draft, _ = assemble(state, selections, 1)
    assert [d.day for d in draft.days if d.rail] == [1, 3, 5]
    for day in draft.days:
        if day.rail:
            assert day.rail.legs[0].origin_station.city == day.origin_city
            assert day.rail.legs[-1].destination_station.city == day.city
            assert day.rail.legs[0].departure_time.date() == day.date


async def test_known_impossible_station_connection_has_evidence():
    state, _ = await prepared()
    d = state["draft_itinerary"].days[2]
    access = next(l for l in d.local_legs if l.route.destination.id == d.rail.legs[0].origin_station.id)
    access.arrival = d.rail.legs[0].departure_time - timedelta(minutes=1)
    i = issue(state, "TRANSPORT_CONFLICT")
    assert i.blocking and i.evidence["buffer_minutes"] > 1 and i.evidence_ids


async def test_unknown_cost_does_not_replan():
    state, context = await prepared()
    draft = state["draft_itinerary"]
    draft.days[0].costs[0].amount = None
    draft.costs = reconcile(draft, state["constraints"].total_budget)
    assert not issue(state, "BUDGET_PARTIAL").blocking
    output = await critique(state, context)
    assert output["status"] == "partial" and "replanning_count" not in output


async def test_estimated_overflow_is_risk_not_confirmed():
    state, context = await prepared()
    draft = state["draft_itinerary"]
    estimate = next(c for d in draft.days for c in d.costs if c.source == "estimate")
    estimate.amount = 500000
    draft.costs = reconcile(draft, state["constraints"].total_budget)
    assert draft.costs.known_cost < draft.costs.budget_limit < draft.costs.estimated_cost
    assert not issue(state, "BUDGET_RISK").blocking
    assert (await critique(state, context))["status"] == "partial"


async def test_known_lower_bound_budget_conflict_persists_after_attempt():
    state, _ = await demo(budget=20000)
    assert state["status"] == "conflict" and state["replanning_count"] > 0
    i = next(i for i in state["validation_result"].issues if i.type == "BUDGET_EXCEEDED")
    assert i.blocking and i.evidence["known_cost"] > i.evidence["budget_limit"]
    assert strict_replanning(state, "trippilot") is False


async def hotel_state():
    from app.core.config import Settings
    from app.schemas.travel import Constraints
    from app.services.engine import create_context, execute

    context = create_context(Settings(rail_provider="dataset"), mode="fixture")
    state = await execute(
        {"user_query": "2026-10-10 杭州两天，预算3000元", "constraints": Constraints(recommend_hotels=True)},
        context,
    )
    state.update(
        draft_itinerary=state["final_itinerary"],
        replanning_count=0,
        validation_history=[],
        issue_signature="",
    )
    return state, context


async def test_unknown_hotel_route_does_not_reselect():
    state, context = await hotel_state()
    for r in state["accommodation"]:
        for h in r.candidates:
            h.route = h.station_route = None
    output = await critique(state, context)
    assert any(i.type == "HOTEL_ROUTE_UNVERIFIED" for i in output["validation_result"].issues)
    assert "accommodation_reselections" not in output and "replanning_count" not in output
    assert output["status"] == "partial"


async def test_known_excessive_hotel_route_blocks():
    state, context = await hotel_state()
    r = state["accommodation"][0]
    h = next(h for h in r.candidates if h.id == r.selected_hotel_id)
    h.route.duration = 100
    i = issue(state, "HOTEL_TOO_FAR")
    assert i.blocking and i.evidence["route_minutes"] == 100
    assert (await critique(state, context))["accommodation_reselections"] == 1


def test_exact_dedup_preserves_distinct_targets():
    a = Issue(
        type="OPENING_HOURS_UNVERIFIED",
        severity="warning",
        status="unverified",
        day=1,
        activity_id="a",
        message="unknown",
        suggestion="confirm",
    )
    b = a.model_copy(update={"activity_id": "b"})
    result = finalize_validation(ValidationResult(valid=True, issues=[a, a.model_copy(), b]))
    assert len(result.issues) == result.unverified_count == 2 and result.valid


@pytest.mark.parametrize("status,severity", [("unverified", "warning"), ("informational", "info")])
def test_nonconfirmed_issue_cannot_block(status, severity):
    with pytest.raises(ValidationError):
        Issue(
            type="UNKNOWN",
            status=status,
            severity=severity,
            blocking=True,
            message="unknown",
            suggestion="confirm",
        )


def test_strict_replan_no_actual_conflict_is_na():
    assert (
        strict_replanning({"validation_history": [{"blocking": [], "unverified_count": 10}]}, "trippilot")
        is None
    )
    assert strict_replanning({}, "baseline") is None


def test_strict_replan_requires_requested_repair_and_subsequent_pass():
    conflict = {"type": "WEATHER_CONFLICT", "day": 1, "activity_id": "a"}
    state = {
        "validation_history": [{"blocking": [conflict], "replanning_requested": False}, {"blocking": []}]
    }
    assert strict_replanning(state, "trippilot") is False
    state["validation_history"][0]["replanning_requested"] = True
    assert strict_replanning(state, "trippilot") is True
    assert strict_replanning(state, "trippilot", True) is False
