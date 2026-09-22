import json

import pytest
from evals.v1_2.schema import load_cases
from evals.v1_2_2.evaluator import fraction, summarize, tool_metrics
from evals.v1_2_2.runner import append_result, read_results, run_case

from app.core.config import Settings


def test_exact_fifty_reviewed_cases_and_no_label_in_request():
    cases = load_cases()
    assert len(cases) == 50
    assert all(not any(k.startswith("expected_") for k in c.request.model_dump()) for c in cases)
    assert all(sum(c.category == group for c in cases) == 10 for group in "ABCDE")


def test_tool_selection_micro_counts():
    result = tool_metrics(["a", "b"], ["a", "c", "c"])
    assert result["exact"] == 0
    assert result["precision"] == result["recall"] == result["f1"] == 0.5
    assert result["tp"] == 1 and result["predicted"] == 2
    assert fraction(0, 0)["rate"] is None


def test_resume_signature_and_durable_append(tmp_path):
    path = tmp_path / "r.jsonl"
    append_result(path, {"case_id": "A01", "signature": "abc", "metrics": {}})
    assert read_results(path, "abc")[0]["case_id"] == "A01"
    with pytest.raises(ValueError):
        read_results(path, "different")
    assert json.loads(path.read_text())["signature"] == "abc"


@pytest.mark.parametrize("system", ["trippilot", "baseline"])
async def test_benchmark_uses_actual_execution_and_same_evaluator(system):
    case = load_cases()[0]
    row = await run_case(
        case,
        system,
        Settings(protocols_enabled=False, rail_provider="dataset"),
        "fixture-test",
        fixture_model=True,
    )
    assert row["model_mode"] == "fixture"
    assert row["usage"]["tool_calls"] > 0 and row["observed"]["final_itinerary"]
    assert row["usage"]["total_tokens"] is None
    summary = summarize([row])
    assert summary["task_success"]["total"] == 1
    if system == "baseline":
        assert summary["routing_accuracy"]["rate"] is None
        assert not any(t["agent"] == "Critic" or t["agent"].startswith("A2A") for t in row["trace"])


async def test_correct_budget_rejection_not_false_success():
    case = next(c for c in load_cases() if c.id == "B01")
    row = await run_case(
        case,
        "trippilot",
        Settings(protocols_enabled=False, rail_provider="dataset"),
        "fixture",
        fixture_model=True,
    )
    assert row["status"] == "conflict" and row["metrics"]["task_success"]
    assert not row["metrics"]["hard_constraints"]["budget"]


def test_resume_recovers_torn_last_record_without_losing_completed(tmp_path):
    path = tmp_path / "result.jsonl"
    append_result(path, {"case_id": "A01", "signature": "abc"})
    with path.open("ab") as file:
        file.write(b'{"case_id":')
    assert len(read_results(path, "abc")) == 1
    assert path.with_suffix(".jsonl.partial").exists()
    assert len(path.read_text().splitlines()) == 1


def test_benchmark_input_does_not_turn_defaults_into_explicit_overrides():
    case = next(c for c in load_cases() if c.id == "E01")
    assert "travel_pace" not in case.request.constraints.model_fields_set
    assert "preferences" not in case.request.constraints.model_fields_set
    assert "activity_end" not in case.request.constraints.model_fields_set


async def test_evaluator_detects_fabricated_dataset_availability():
    from evals.v1_2_2.evaluator import unsupported_claims

    from app.schemas.travel import Constraints
    from app.services.engine import create_context, execute

    ctx = create_context(Settings(rail_provider="dataset"), mode="fixture", demo=True)
    state = await execute(
        {
            "user_query": "10月10日从北京到上海两天，预算4000元",
            "constraints": Constraints(compare_transport=True, transport_mode="flight"),
        },
        ctx,
    )
    assert unsupported_claims(state)["unsupported"] == 0
    state["final_itinerary"].days[0].flight = (
        state["final_itinerary"].days[0].flight.model_copy(update={"provider_mode": "LIVE"})
    )
    assert unsupported_claims(state)["unsupported"] > 0


async def test_benchmark_per_case_model_guard_stops_safely(monkeypatch):
    from evals.v1_2 import runner

    monkeypatch.setattr(runner, "MAX_CALLS_PER_CASE", 1)
    row = await runner.run_case(
        load_cases()[0],
        "trippilot",
        Settings(protocols_enabled=False, rail_provider="dataset"),
        "guard-test",
        fixture_model=True,
    )
    assert row["usage"]["qwen_calls"] == 1
    assert not row["metrics"]["task_success"]
    assert "BUDGET_EXHAUSTED" in row["metrics"]["failure_reasons"]


@pytest.mark.parametrize("variant", ["invalid_then_valid", "omitted_defaults"])
async def test_baseline_tool_contract_and_error_observation(monkeypatch, variant):
    from types import SimpleNamespace

    from evals.baseline import single_agent

    from app.agents.supervisor import parse_fixture
    from app.mcp.schemas import CONTRACTS
    from app.schemas.travel import Constraints
    from app.services.engine import create_context

    context = create_context(Settings(), mode="fixture")
    context.model = SimpleNamespace(name="scripted", status="MOCK")
    packets = []

    async def decide(client, payload, schema, budget, usage):
        if schema is Constraints:
            return Constraints.model_validate(parse_fixture(payload["query"], context.now.date()))
        packets.append(payload)
        if variant == "invalid_then_valid" and len(packets) == 1:
            return schema(
                kind="actions",
                calls=[{"tool": "search_poi", "arguments": {"city": "杭州", "category": "indoor"}}],
            )
        pending = payload["pending_queries"]
        if pending:
            if variant == "omitted_defaults":
                pending = [
                    {
                        "tool": item["tool"],
                        "arguments": CONTRACTS[item["tool"]][0]
                        .model_validate(item["arguments"])
                        .model_dump(mode="json", exclude_defaults=True),
                    }
                    for item in pending
                ]
            return schema(kind="actions", calls=pending)
        return schema(kind="final", selections=payload["suggested_selections"])

    monkeypatch.setattr(single_agent, "structured_call", decide)
    result = await single_agent.execute_single({"user_query": "2026-10-10 杭州一天，预算3000元。"}, context)
    assert result["status"] == "completed"
    assert result["final_itinerary"].days[0].activities
    assert len(packets[0]["tool_schemas"]) == 7
    if variant == "invalid_then_valid":
        assert packets[1]["tool_observations"][-1]["error_code"] == "INVALID_INPUT"
    assert not any(t.agent == "Critic" or t.agent.startswith("A2A") for t in context.trace)
