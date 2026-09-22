"""Deterministic evaluator. Labels only enter here, never model payloads."""

import math
import statistics
from datetime import time

from app.agents.critic import validate_itinerary
from app.harness.runtime import TOOL_NAMES
from app.providers.amap import straight_distance


def tool_metrics(required, actual):
    required, actual = set(required), set(actual)
    tp = len(required & actual)
    precision = tp / len(actual) if actual else (1.0 if not required else 0.0)
    recall = tp / len(required) if required else 1.0
    return {
        "exact": int(required == actual),
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0,
        "tp": tp,
        "predicted": len(actual),
        "required": len(required),
        "actual": sorted(actual),
    }


def accommodation_valid(state):
    recommendations = state.get("accommodation", [])
    itinerary = state.get("final_itinerary")
    if not itinerary or not recommendations:
        return False
    cities = {d.city for d in itinerary.days}
    if not cities <= {r.city for r in recommendations}:
        return False
    for r in recommendations:
        h = next((h for h in r.candidates if h.id == r.selected_hotel_id), None)
        if (
            not h
            or not h.coordinates
            or not r.reasons
            or not r.recommended_area
            or h.realtime_price is not None
        ):
            return False
        e = state.get("evidence", {}).get(h.evidence_id)
        if not e or (h.source == "amap_live") != (e.source_kind == "live"):
            return False
        pois = [a.poi for d in itinerary.days if d.city == r.city for a in d.activities]
        if not pois or any(
            not p.coordinates or straight_distance(h.coordinates, p.coordinates) > 15000
            for p in pois
        ):
            return False
    return True


def preference_value(constraints, field):
    if field == "interests":
        mapping = {"历史": "history", "夜景": "night_view", "自然": "nature"}
        return [mapping[p] for p in constraints.preferences if p in mapping]
    return getattr(constraints, field, None)


def preference_checks(expected, constraints):
    if not constraints:
        return False
    return all(
        (set(value) <= set(preference_value(constraints, key) or []))
        if isinstance(value, list)
        else preference_value(constraints, key) == value
        for key, value in expected.items()
    )


def unsupported_claims(state):
    claims = bad = 0
    evidence = state.get("evidence", {})
    itinerary = state.get("final_itinerary")
    if itinerary:
        known_rail = {r.id: r for r in state.get("transport_options", [])}
        known_flight = {f.id: f for f in state.get("flight_options", [])}
        for day in itinerary.days:
            if day.rail:
                claims += 1
                bad += int(
                    day.rail.id not in known_rail
                    or day.rail.model_dump() != known_rail[day.rail.id].model_dump()
                )
                for leg in day.rail.legs:
                    claims += 1
                    e = evidence.get(leg.evidence_id)
                    bad += int(
                        e is None
                        or (
                            e.source_kind in {"dataset", "mock"}
                            and leg.availability == "available"
                        )
                    )
            if day.flight:
                f = day.flight
                claims += 2
                e = evidence.get(f.evidence_id)
                bad += int(
                    f.id not in known_flight
                    or f.model_dump() != known_flight[f.id].model_dump()
                )
                bad += int(
                    e is None
                    or (
                        e.source_kind == "dataset"
                        and (
                            f.provider_mode != "DATASET"
                            or f.availability_status == "available"
                        )
                    )
                )
    for r in state.get("accommodation", []):
        for h in r.candidates:
            claims += 3
            e = evidence.get(h.evidence_id)
            bad += int(h.realtime_price is not None) + int(
                h.availability_status != "unknown"
            )
            bad += int(
                e is None or (h.source == "amap_live") != (e.source_kind == "live")
            )
    for comparison in state.get("transport_comparisons", []):
        for c in comparison.candidates:
            claims += 1
            bad += int(
                c.estimate.access_source not in {"estimated", "unknown", "provider"}
                or c.estimate.estimated_total_minutes != c.estimate.calculated_total
            )
    return {"unsupported": bad, "claims": claims}


def evaluate(case, state, contexts, system):
    itinerary = state.get("final_itinerary")
    constraints = state.get("constraints")
    validation = (
        validate_itinerary(itinerary, constraints, state)
        if itinerary and constraints
        else None
    )
    issues = (
        [i.type for i in validation.issues if i.severity == "high"]
        if validation
        else ["NO_ITINERARY"]
    )
    hard = {}
    for kind, value in case.hard_constraints.items():
        ok = False
        if itinerary and constraints:
            if kind == "destinations":
                ok = set(value) <= {d.city for d in itinerary.days if d.activities}
            elif kind == "days":
                ok = len(itinerary.days) == value
            elif kind == "start_date":
                ok = (
                    bool(itinerary.days) and itinerary.days[0].date.isoformat() == value
                )
            elif kind == "budget":
                ok = (
                    not itinerary.costs.unknown_items
                    and itinerary.costs.estimated_total <= value
                )
            elif kind == "max_attractions":
                ok = all(len(d.activities) <= value for d in itinerary.days)
            elif kind == "activity_end":
                ok = all(
                    a.end.time() <= time.fromisoformat(value)
                    for d in itinerary.days
                    for a in d.activities
                )
            elif kind == "arrival_deadline":
                ok = "ARRIVAL_DEADLINE" not in issues and all(
                    (
                        d.flight.arrival_time
                        if d.flight
                        else d.rail.legs[-1].arrival_time
                    ).time()
                    <= time.fromisoformat(value)
                    for d in itinerary.days
                    if d.rail or d.flight
                )
            elif kind == "transport_mode":
                ok = all(
                    bool(d.rail) if value == "rail" else bool(d.flight)
                    for d in itinerary.days
                    if d.city != d.origin_city
                )
            elif kind == "transfer_buffer":
                ok = all(
                    (b.departure_time - a.arrival_time).total_seconds() / 60 >= value
                    for d in itinerary.days
                    if d.rail
                    for a, b in zip(d.rail.legs, d.rail.legs[1:])
                )
            elif kind == "weather":
                ok = all(
                    a.poi.environment == "indoor"
                    for d in itinerary.days
                    for a in d.activities
                )
            elif kind == "indoor_days":
                ok = all(
                    a.poi.environment == "indoor"
                    for d in itinerary.days
                    if d.day in value
                    for a in d.activities
                )
            elif kind in {"memory", "memory_override"}:
                ok = preference_checks(value, constraints)
            elif kind == "accommodation":
                ok = accommodation_valid(state)
            else:
                raise ValueError("Unknown evaluator constraint: " + kind)
        hard[kind] = bool(ok)
    ctx = contexts[-1]
    tools = [
        TOOL_NAMES.get(c["tool"], c["tool"])
        for context in contexts
        for c in context.registry.calls
    ]
    ts = tool_metrics(case.required_tools, tools)
    source = unsupported_claims(state)
    runtime_fail = state.get("status") in {
        "failed",
        "cancelled",
        "needs_clarification",
    } or bool(state.get("stop_reason"))
    correct_rejection = (
        case.expected_failure_allowed
        and state.get("status") == "conflict"
        and bool(issues)
        and not runtime_fail
    )
    sections = (
        bool(itinerary)
        and (not case.requires_hotel or accommodation_valid(state))
        and (
            not case.requires_transport_comparison
            or bool(state.get("transport_comparisons"))
        )
    )
    success = bool(
        not runtime_fail
        and source["unsupported"] == 0
        and (correct_rejection or (sections and all(hard.values()) and not issues))
    )
    route_success = (
        None
        if system == "baseline"
        else state.get("routing_plan", []) == case.expected_agent_routes
        and all(
            any(
                t.agent
                in (
                    {
                        "Transport": "A2A Transport Agent",
                        "Local Travel": "A2A Local Travel Agent",
                    }.get(role, ""),
                    role,
                    "Rail Search" if role == "Transport" else "Amap POI",
                )
                for t in ctx.trace
            )
            for role in case.expected_agent_routes
        )
    )
    replanning = None
    if case.requires_replanning and system != "baseline":
        replanning = bool(
            any(t.agent == "Critic" and t.status == "failed" for t in ctx.trace)
            and state.get("replanning_count", 0) > 0
            and hard.get("weather", False)
            and not runtime_fail
        )
    memory = None
    override = None
    if case.requires_memory:
        expected = {
            **case.soft_preferences,
            **case.hard_constraints.get("memory", {}),
            **case.hard_constraints.get("memory_override", {}),
        }
        memory = bool(
            ctx.memory_status.get("long_term_loaded")
            and preference_checks(expected, constraints)
        )
    if "memory_override" in case.hard_constraints:
        override = hard["memory_override"]
    transport = None
    if "Transport" in case.expected_agent_routes:
        transport = bool(
            itinerary
            and not runtime_fail
            and not any(
                x in issues
                for x in [
                    "MISSING_TRANSPORT",
                    "TRANSPORT_HALLUCINATION",
                    "FLIGHT_HALLUCINATION",
                    "FLIGHT_UNAVAILABLE",
                    "TRANSPORT_UNAVAILABLE",
                    "TRANSFER_RISK",
                    "TRAIN_DEPARTURE_RISK",
                    "ARRIVAL_DEADLINE",
                    "TRANSPORT_MODE",
                ]
            )
        )
        if state.get("transport_comparisons"):
            transport = transport and all(
                c.estimate.calculated_total == c.estimate.estimated_total_minutes
                for r in state["transport_comparisons"]
                for c in r.candidates
            )
    reasons = []
    if runtime_fail:
        reasons.append(state.get("stop_reason") or state.get("status", "unknown"))
    if not correct_rejection:
        reasons.extend("constraint:" + k for k, v in hard.items() if not v)
        reasons.extend(issues)
    if not sections and not correct_rejection:
        reasons.append("MISSING_REQUIRED_SECTION")
    if source["unsupported"]:
        reasons.append("UNSUPPORTED_CLAIM")
    return {
        "task_success": success,
        "correct_rejection": correct_rejection,
        "hard_constraints": hard,
        "constraint_satisfaction": {"passed": sum(hard.values()), "total": len(hard)},
        "routing_accuracy": route_success,
        "tool_selection": ts,
        "replanning_success": replanning,
        "preference_adherence": memory,
        "memory_override": override,
        "accommodation_validity": accommodation_valid(state)
        if case.requires_hotel
        else None,
        "transport_feasibility": transport,
        "unsupported_claims": source,
        "failure_reasons": list(dict.fromkeys(reasons)),
    }


def fraction(passed, total):
    return {"passed": passed, "total": total, "rate": passed / total if total else None}


def summarize(rows):
    result = {}
    for key in [
        "task_success",
        "routing_accuracy",
        "replanning_success",
        "preference_adherence",
        "memory_override",
        "accommodation_validity",
        "transport_feasibility",
    ]:
        values = [r["metrics"][key] for r in rows if r["metrics"][key] is not None]
        result[key] = fraction(sum(values), len(values))
    result["constraint_satisfaction"] = fraction(
        sum(r["metrics"]["constraint_satisfaction"]["passed"] for r in rows),
        sum(r["metrics"]["constraint_satisfaction"]["total"] for r in rows),
    )
    result["tool_exact_match"] = fraction(
        sum(r["metrics"]["tool_selection"]["exact"] for r in rows), len(rows)
    )
    tp = sum(r["metrics"]["tool_selection"]["tp"] for r in rows)
    pred = sum(r["metrics"]["tool_selection"]["predicted"] for r in rows)
    required = sum(r["metrics"]["tool_selection"]["required"] for r in rows)
    precision = tp / pred if pred else 0
    recall = tp / required if required else 0
    result["tool_precision"] = precision
    result["tool_recall"] = recall
    result["tool_f1"] = (
        2 * precision * recall / (precision + recall) if precision + recall else 0
    )
    result["unsupported_claim_rate"] = fraction(
        sum(r["metrics"]["unsupported_claims"]["unsupported"] for r in rows),
        sum(r["metrics"]["unsupported_claims"]["claims"] for r in rows),
    )
    latency = sorted(r["latency_seconds"] for r in rows)
    result["latency_seconds"] = (
        {
            "average": statistics.mean(latency),
            "median": statistics.median(latency),
            "p95": latency[math.ceil(len(latency) * 0.95) - 1],
        }
        if latency
        else None
    )
    for field in [
        "agent_steps",
        "tool_calls",
        "external_calls",
        "qwen_calls",
        "input_tokens",
        "output_tokens",
        "total_tokens",
    ]:
        values = [r["usage"][field] for r in rows if r["usage"][field] is not None]
        result[field] = {
            "average": statistics.mean(values) if values else None,
            "total": sum(values) if values else None,
            "available_cases": len(values),
        }
    return result
