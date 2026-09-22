# TripPilot V1.2.2 Agent Benchmark

状态：complete；Dataset: 50 cases；Category distribution: 10 / 10 / 10 / 10 / 10。

| Metric | TripPilot | Single-Agent | Difference (percentage points) |
|---|---:|---:|---:|
| task_success | 96.000000% | 64.000000% | 31.999999999999996 |
| routing_accuracy | 100.000000% | N/A | N/A |
| replanning_success | 33.333333% | N/A | N/A |
| legacy_replanning_success | 10.000000% | N/A | N/A |
| preference_adherence | 100.000000% | 57.142857% | 42.85714285714286 |
| memory_override | 100.000000% | 33.333333% | 66.66666666666667 |
| accommodation_validity | 100.000000% | 70.000000% | 30.000000000000004 |
| transport_feasibility | 94.285714% | 62.857143% | 31.428571428571427 |
| constraint_satisfaction | 98.706897% | 83.189655% | 15.517241379310342 |
| tool_exact_match | 100.000000% | 46.000000% | 54.0 |
| unsupported_claim_rate | 0.000000% | 0.000000% | 0.0 |
| tool_precision | 100.000000% | 98.907104% | 1.0928961748633892 |
| tool_recall | 100.000000% | 82.648402% | 17.35159817351598 |
| tool_f1 | 100.000000% | 90.049751% | 9.950248756218905 |

## Latency / Cost

{
  "trippilot": {
    "latency_seconds": {
      "average": 17.032756613336968,
      "median": 14.047114979533944,
      "p95": 29.046813624969218
    },
    "agent_steps": {
      "average": 2.64,
      "total": 132,
      "available_cases": 50
    },
    "tool_calls": {
      "average": 14.86,
      "total": 743,
      "available_cases": 50
    },
    "external_calls": {
      "average": 24.38,
      "total": 1219,
      "available_cases": 50
    },
    "qwen_calls": {
      "average": 3.66,
      "total": 183,
      "available_cases": 50
    },
    "input_tokens": {
      "average": 20998.7,
      "total": 1049935,
      "available_cases": 50
    },
    "output_tokens": {
      "average": 601.7,
      "total": 30085,
      "available_cases": 50
    },
    "total_tokens": {
      "average": 21600.4,
      "total": 1080020,
      "available_cases": 50
    }
  },
  "baseline": {
    "latency_seconds": {
      "average": 31.107730066577204,
      "median": 27.744447874982143,
      "p95": 68.40333991701482
    },
    "agent_steps": {
      "average": 4.5,
      "total": 225,
      "available_cases": 50
    },
    "tool_calls": {
      "average": 6.92,
      "total": 346,
      "available_cases": 50
    },
    "external_calls": {
      "average": 13.38,
      "total": 669,
      "available_cases": 50
    },
    "qwen_calls": {
      "average": 5.46,
      "total": 273,
      "available_cases": 50
    },
    "input_tokens": {
      "average": 21375.51020408163,
      "total": 1047400,
      "available_cases": 49
    },
    "output_tokens": {
      "average": 1154.7551020408164,
      "total": 56583,
      "available_cases": 49
    },
    "total_tokens": {
      "average": 22530.26530612245,
      "total": 1103983,
      "available_cases": 49
    }
  }
}

## Failed cases

- trippilot B01 (B): BUDGET_EXHAUSTED, constraint:budget, BUDGET_EXCEEDED
- trippilot B02 (B): constraint:budget
- baseline A01 (A): MAX_STEPS, constraint:destinations, MISSING_DESTINATION, EMPTY_DAY
- baseline A02 (A): MAX_STEPS, constraint:destinations, MISSING_DESTINATION, EMPTY_DAY
- baseline A03 (A): MAX_STEPS, constraint:destinations, MISSING_DESTINATION, EMPTY_DAY
- baseline A04 (A): MAX_STEPS, constraint:destinations, MISSING_DESTINATION, EMPTY_DAY
- baseline A05 (A): MAX_STEPS, constraint:destinations, MISSING_DESTINATION, EMPTY_DAY
- baseline A06 (A): MAX_STEPS, constraint:destinations, MISSING_DESTINATION, EMPTY_DAY
- baseline A07 (A): MAX_STEPS, constraint:destinations, MISSING_DESTINATION, EMPTY_DAY
- baseline A08 (A): MAX_STEPS, constraint:destinations, MISSING_DESTINATION, EMPTY_DAY
- baseline A09 (A): MAX_STEPS, constraint:destinations, MISSING_DESTINATION, EMPTY_DAY
- baseline A10 (A): MAX_STEPS, constraint:destinations, MISSING_DESTINATION, EMPTY_DAY
- baseline B02 (B): constraint:budget
- baseline B03 (B): MAX_STEPS
- baseline B05 (B): constraint:arrival_deadline, ARRIVAL_DEADLINE
- baseline C02 (C): INVALID_OUTPUT, constraint:destinations, constraint:days, constraint:start_date, constraint:budget, constraint:weather, NO_ITINERARY, MISSING_REQUIRED_SECTION
- baseline D01 (D): INVALID_OUTPUT, constraint:destinations, constraint:days, constraint:start_date, constraint:budget, constraint:transport_mode, NO_ITINERARY, MISSING_REQUIRED_SECTION
- baseline E01 (E): INVALID_OUTPUT, constraint:destinations, constraint:days, constraint:start_date, constraint:budget, constraint:memory, NO_ITINERARY, MISSING_REQUIRED_SECTION
- baseline E02 (E): INVALID_OUTPUT, constraint:destinations, constraint:days, constraint:start_date, constraint:budget, constraint:memory_override, NO_ITINERARY, MISSING_REQUIRED_SECTION
- baseline E10 (E): INVALID_OUTPUT, constraint:destinations, constraint:days, constraint:start_date, constraint:budget, constraint:memory_override, NO_ITINERARY, MISSING_REQUIRED_SECTION

## Limitations

- 单次运行，无置信区间或因果性能提升声明。
- 固定合成高德/铁路/航班证据；真实LIVE能力由单独smoke验证。
- 双方共用类型合同、确定性装配和费用计算；Baseline无专家分解、独立Critic或重规划。
- 未知事实不算已满足；正确不可满足可算Task Success，但原始约束满足单列。
- 模型服务可能随时间变化；已保存固定数据与代码指纹。
