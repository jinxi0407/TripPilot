"""Serial paid-model benchmark. Run only with explicit user authorization."""

import argparse
import asyncio
import hashlib
import json
import os
from datetime import UTC, datetime
from time import perf_counter

from app.core.config import Settings
from app.core.logging import configure_logging
from app.persistence.memory import extract_preferences
from app.schemas.product import TravelPreferences
from app.schemas.travel import Constraints
from app.services.engine import create_context, execute
from app.services.runs import RunService

from evals.baseline.single_agent import execute_single
from evals.v1_2.evaluator import evaluate, summarize
from evals.v1_2.schema import DIRECTORY, ROOT, file_hash, load_cases

MAX_CALLS_PER_CASE = 12
CASE_TIMEOUT_SECONDS = 240
MAX_TOTAL_CALLS = 1200
MAX_TOTAL_REPORTED_TOKENS = 6_000_000
MAX_RUNTIME_SECONDS = 8 * 3600


def signature(settings):
    files = list((ROOT / "backend/app").rglob("*.py")) + list(
        (ROOT / "backend/app/providers/data").glob("*.json")
    )
    files += (
        [DIRECTORY / name for name in ["runner.py", "schema.py", "evaluator.py"]]
        + list((ROOT / "evals/baseline").glob("*.py"))
        + [DIRECTORY / "benchmark_50.jsonl"]
    )
    hashes = {str(p.relative_to(ROOT)): file_hash(p) for p in sorted(files)}
    payload = {
        "model": settings.qwen_model,
        "temperature": 0,
        "files": hashes,
        "policy": settings.runtime_policy.model_dump(),
        "per_case_calls": MAX_CALLS_PER_CASE,
        "max_total_calls": MAX_TOTAL_CALLS,
        "max_reported_tokens": MAX_TOTAL_REPORTED_TOKENS,
        "provider_mode": "fixture",
        "rail": "dataset",
        "flight": "dataset",
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest(), payload


def append_result(path, row):
    with path.open("a") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def read_results(path, expected_signature):
    if not path.exists():
        return []
    rows = []
    raw = path.read_bytes()
    lines = raw.splitlines(keepends=True)
    accepted = b""
    for index, line in enumerate(lines):
        if line.strip():
            try:
                row = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                if index != len(lines) - 1 or line.endswith(b"\n"):
                    raise ValueError(
                        "Corrupt complete result record; manual inspection required"
                    ) from None
                path.with_suffix(path.suffix + ".partial").write_bytes(line)
                path.write_bytes(accepted)
                break
            if row["signature"] != expected_signature:
                raise ValueError(
                    "Result signature mismatch; archive previous run before full rerun"
                )
            rows.append(row)
            accepted += line
    if len(rows) != len({r["case_id"] for r in rows}):
        raise ValueError("Duplicate case result")
    return rows


async def run_case(case, system, settings, run_signature, fixture_model=False):
    contexts = []
    started = perf_counter()

    def factory(config, mode, demo, scenario):
        used = sum(c.budget.models for c in contexts)
        policy = config.runtime_policy.model_copy(
            update={
                "max_model_calls": max(1, MAX_CALLS_PER_CASE - used),
                "total_timeout_seconds": max(
                    1, CASE_TIMEOUT_SECONDS - (perf_counter() - started)
                ),
            }
        )
        local = config.model_copy(update={"runtime_policy": policy})
        ctx = create_context(
            local,
            mode="fixture" if fixture_model else "live",
            provider_mode="fixture",
            scenario=case.scenario,
        )
        contexts.append(ctx)
        return ctx

    config = settings.model_copy(
        update={
            "memory_database": ":memory:",
            "rail_provider": "dataset",
            "flight_provider": "dataset",
        }
    )
    service = RunService(
        config,
        context_factory=factory,
        executor=execute if system == "trippilot" else execute_single,
    )
    if case.stored_preferences:
        service.preferences.save(case.stored_preferences, True)
    record = None
    try:
        request = case.request.model_copy(
            update={"mode": "fixture" if fixture_model else "live"}
        )
        # Replay actual planning continuation when a transcript contains a day correction.
        if len(case.turns) > 1 and "第二天" in case.turns[-1]:
            initial = request.model_copy(
                update={
                    "query": case.turns[0],
                    "constraints": Constraints.model_validate(
                        {
                            **request.constraints.model_dump(exclude_unset=True),
                            "indoor_days": [],
                        }
                    ),
                }
            )
            previous = service.create(initial)
            await asyncio.wait_for(previous.task, timeout=CASE_TIMEOUT_SECONDS)
            request = request.model_copy(
                update={
                    "query": case.turns[-1],
                    "constraints": None,
                    "session_id": previous.request.session_id,
                }
            )
        elif case.turns:
            for turn in case.turns:
                preferences = extract_preferences(turn)
                if preferences:
                    service.preferences.update(
                        TravelPreferences.model_validate(preferences), True
                    )
        if sum(c.budget.models for c in contexts) >= MAX_CALLS_PER_CASE:
            raise TimeoutError("case call guard")
        record = service.create(request)
        await asyncio.wait_for(
            record.task,
            timeout=max(1, CASE_TIMEOUT_SECONDS - (perf_counter() - started)),
        )
        state = record.state
    except Exception as exc:  # noqa: BLE001 - benchmark boundary saves sanitized failures, never raw SDK text
        state = record.state if record else {"status": "failed"}
        state = {
            **state,
            "status": "failed",
            "stop_reason": "DEADLINE_EXCEEDED"
            if isinstance(exc, TimeoutError)
            else "PROVIDER_FAILURE",
        }
    finally:
        await service.close()
    if not contexts:
        contexts.append(create_context(config, mode="fixture"))
    metrics = evaluate(case, state, contexts, system)
    usage = [u for c in contexts for u in c.usage]
    complete = bool(usage) and all(u is not None for u in usage)
    input_tokens = sum(u.input_tokens for u in usage if u) if complete else None
    output_tokens = sum(u.output_tokens for u in usage if u) if complete else None
    observed = {
        k: state.get(k)
        for k in [
            "constraints",
            "final_itinerary",
            "validation_result",
            "transport_comparisons",
            "accommodation",
            "routing_plan",
            "replanning_count",
        ]
    }

    def encode(value):
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if isinstance(value, list):
            return [encode(x) for x in value]
        if isinstance(value, dict):
            return {k: encode(v) for k, v in value.items()}
        return value

    return {
        "case_id": case.id,
        "category": case.category,
        "system": system,
        "signature": run_signature,
        "model": settings.qwen_model,
        "model_mode": "fixture" if fixture_model else "live",
        "temperature": 0,
        "status": state.get("status", "failed"),
        "latency_seconds": perf_counter() - started,
        "metrics": metrics,
        "usage": {
            "agent_steps": sum(sum(c.steps.values()) for c in contexts),
            "tool_calls": sum(c.budget.tools for c in contexts),
            "external_calls": sum(c.budget.external for c in contexts),
            "qwen_calls": sum(c.budget.models for c in contexts),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens if complete else None,
            "reported_tokens": sum(
                u.input_tokens + u.output_tokens for u in usage if u
            ),
            "unavailable_usage_calls": sum(u is None for u in usage),
        },
        "observed": encode(observed),
        "providers": contexts[-1].provider_status(),
        "runtime": contexts[-1].runtime_status(),
        "trace": [e.model_dump(mode="json") for c in contexts for e in c.trace],
    }


def report(all_rows, run_signature, configuration):
    systems = {s: summarize(all_rows[s]) for s in ["trippilot", "baseline"]}
    complete = all(len(all_rows[s]) == 50 for s in all_rows)
    comparison = {}
    for key in systems["trippilot"]:
        a, b = systems["trippilot"][key], systems["baseline"][key]
        if isinstance(a, dict) and "rate" in a:
            comparison[key] = {
                "trippilot": a["rate"],
                "baseline": b["rate"],
                "percentage_point_difference": 100 * (a["rate"] - b["rate"])
                if a["rate"] is not None and b["rate"] is not None
                else None,
            }
    failed = [
        {
            "system": s,
            "id": r["case_id"],
            "category": r["category"],
            "reasons": r["metrics"]["failure_reasons"],
        }
        for s, rows in all_rows.items()
        for r in rows
        if not r["metrics"]["task_success"]
    ]
    summary = {
        "status": "complete" if complete else "partial",
        "signature": run_signature,
        "configuration": configuration,
        "dataset_size": 50,
        "category_distribution": dict.fromkeys("ABCDE", 10),
        "executed": {s: len(r) for s, r in all_rows.items()},
        "metrics": systems,
        "comparison": comparison,
        "failed_cases": failed,
        "limitations": [
            "单次运行，无置信区间或因果性能提升声明。",
            "固定合成高德/铁路/航班证据；真实LIVE能力由单独smoke验证。",
            "双方共用类型合同、确定性装配和费用计算；Baseline无专家分解、独立Critic或重规划。",
            "未知事实不算已满足；正确不可满足可算Task Success，但原始约束满足单列。",
            "模型服务可能随时间变化；已保存固定数据与代码指纹。",
        ],
    }
    (DIRECTORY / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2)
    )
    lines = [
        "# TripPilot V1.2 Agent Benchmark",
        "",
        f"状态：{summary['status']}；Dataset: 50 cases；Category distribution: 10 / 10 / 10 / 10 / 10。",
        "",
        "| Metric | TripPilot | Single-Agent | Difference (percentage points) |",
        "|---|---:|---:|---:|",
    ]

    def fmt(value):
        return "N/A" if value is None else f"{value * 100:.6f}%"

    for key, row in comparison.items():
        delta = row["percentage_point_difference"]
        lines.append(
            f"| {key} | {fmt(row['trippilot'])} | {fmt(row['baseline'])} | {delta if delta is not None else 'N/A'} |"
        )
    for key in ["tool_precision", "tool_recall", "tool_f1"]:
        lines.append(
            f"| {key} | {fmt(systems['trippilot'][key])} | {fmt(systems['baseline'][key])} | {(systems['trippilot'][key] - systems['baseline'][key]) * 100} |"
        )
    lines += [
        "",
        "## Latency / Cost",
        "",
        json.dumps(
            {
                s: {
                    k: v
                    for k, v in m.items()
                    if k
                    in [
                        "latency_seconds",
                        "agent_steps",
                        "tool_calls",
                        "external_calls",
                        "qwen_calls",
                        "input_tokens",
                        "output_tokens",
                        "total_tokens",
                    ]
                }
                for s, m in systems.items()
            },
            ensure_ascii=False,
            indent=2,
        ),
        "",
        "## Failed cases",
        "",
    ]
    lines += [
        f"- {r['system']} {r['id']} ({r['category']}): {', '.join(r['reasons'])}"
        for r in failed
    ] or ["无。"]
    lines += ["", "## Limitations", ""] + ["- " + x for x in summary["limitations"]]
    (DIRECTORY / "summary.md").write_text("\n".join(lines) + "\n")
    metrics = systems["trippilot"]
    bullets = []
    for label, key in [
        ("旅行任务成功", "task_success"),
        ("硬约束满足", "constraint_satisfaction"),
        ("暴雨重规划成功", "replanning_success"),
        ("旅行偏好遵循", "preference_adherence"),
    ]:
        m = metrics[key]
        bullets.append(
            f"- 固定50题、qwen-plus、合成Provider评估中，{label} {m['passed']}/{m['total']}（{fmt(m['rate'])}）；实际已执行 {len(all_rows['trippilot'])}/50 题。"
        )
    bullets.append(
        f"- 工具选择 micro F1 为 {fmt(metrics['tool_f1'])}；来自实际调用集合，不代表真实旅行保证。"
    )
    (DIRECTORY / "resume_metrics.md").write_text(
        "# 实测简历候选数字\n\n"
        + ("\n".join(bullets) if complete else "主评估尚未完整，暂不建议用于简历。")
        + "\n"
    )
    return summary


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-paid-model", action="store_true")
    parser.add_argument("--fixture-model", action="store_true")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument(
        "--system", choices=["both", "trippilot", "baseline"], default="both"
    )
    args = parser.parse_args()
    if not (args.allow_paid_model or args.fixture_model):
        raise SystemExit("需要显式 --allow-paid-model 授权已有模型API调用。")
    configure_logging()
    cases = load_cases()
    settings = Settings(
        protocols_enabled=True,
        protocol_fixture=True,
        rail_provider="dataset",
        flight_provider="dataset",
        memory_database=":memory:",
    )
    settings.runtime_policy.max_model_calls = MAX_CALLS_PER_CASE
    settings.runtime_policy.model_timeout_seconds = 60
    settings.runtime_policy.total_timeout_seconds = CASE_TIMEOUT_SECONDS
    if not args.fixture_model and (
        not settings.model_ready or settings.qwen_model != "qwen-plus"
    ):
        raise SystemExit("Qwen qwen-plus 配置缺失或不匹配。")
    sig, configuration = signature(settings)
    if args.fixture_model:
        raise SystemExit("fixture模型通过单元测试调用run_case，不写入真实结果目录。")
    paths = {
        "trippilot": DIRECTORY / "results_tripilot.jsonl",
        "baseline": DIRECTORY / "results_baseline.jsonl",
    }
    all_rows = {s: read_results(p, sig) for s, p in paths.items()}
    (DIRECTORY / "manifest.json").write_text(
        json.dumps(
            {
                "signature": sig,
                "configuration": configuration,
                "started_at": datetime.now(UTC).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    started = perf_counter()
    for system in ["trippilot", "baseline"] if args.system == "both" else [args.system]:
        done = {r["case_id"] for r in all_rows[system]}
        for case in cases[: args.limit]:
            if case.id in done:
                continue
            spent_calls = sum(
                r["usage"]["qwen_calls"] for rows in all_rows.values() for r in rows
            )
            spent_tokens = sum(
                r["usage"]["reported_tokens"]
                for rows in all_rows.values()
                for r in rows
            )
            if (
                spent_calls + MAX_CALLS_PER_CASE > MAX_TOTAL_CALLS
                or spent_tokens >= MAX_TOTAL_REPORTED_TOKENS
                or sum(r["latency_seconds"] for rows in all_rows.values() for r in rows)
                + perf_counter()
                - started
                > MAX_RUNTIME_SECONDS
            ):
                report(all_rows, sig, configuration)
                print("Benchmark guard reached; saved partial results.", flush=True)
                return
            if signature(settings)[0] != sig:
                report(all_rows, sig, configuration)
                raise SystemExit(
                    "Benchmark code changed; saved partial, full rerun required."
                )
            row = await run_case(case, system, settings, sig)
            append_result(paths[system], row)
            all_rows[system].append(row)
            if len(all_rows[system]) % 5 == 0 or args.limit < 5:
                print(
                    json.dumps(
                        {
                            "system": system,
                            "completed": len(all_rows[system]),
                            "task_success": sum(
                                r["metrics"]["task_success"] for r in all_rows[system]
                            ),
                            "qwen_calls": sum(
                                r["usage"]["qwen_calls"] for r in all_rows[system]
                            ),
                            "last_case": case.id,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
            report(all_rows, sig, configuration)
    print(
        json.dumps(
            {
                "status": report(all_rows, sig, configuration)["status"],
                "executed": {s: len(r) for s, r in all_rows.items()},
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
