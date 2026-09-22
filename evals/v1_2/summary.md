# TripPilot V1.2 Agent Benchmark

状态：complete。Dataset: **50 cases**；Category distribution: **10 / 10 / 10 / 10 / 10**。两系统分别执行50/50。

模型：qwen-plus；temperature=0；代码/数据指纹：`7772d756617b9d9324654893909220ba71d72c236696b30463bf1f0cbe89a4bb`。

| 指标 | TripPilot | Single-Agent | 百分点差（TripPilot − Baseline） |
|---|---:|---:|---:|
| Task Success | 44/50（88%） | 32/50（64%） | +24 |
| Constraint Satisfaction | 229/232（98.706896%） | 204/232（87.931034%） | +10.775862 |
| Agent Routing Accuracy | 50/50（100%） | N/A | N/A |
| Tool Selection Exact Match | 50/50（100%） | 25/50（50%） | +50 |
| Tool Precision | 100% | 95.408163% | +4.591836 |
| Tool Recall | 100% | 85.388127% | +14.611872 |
| Tool F1 | 100% | 90.120481% | +9.879518 |
| Replanning Success | 1/10（10%） | N/A | N/A |
| Preference Adherence | 7/7（100%） | 5/7（71.428571%） | +28.571428 |
| Memory Override | 3/3（100%） | 2/3（66.666666%） | +33.333333 |
| Accommodation Validity | 10/10（100%） | 8/10（80%） | +20 |
| Transport Feasibility | 33/35（94.285714%） | 23/35（65.714285%） | +28.571428 |
| Unsupported Claim Rate（越低越好） | 0/267（0%） | 0/264（0%） | +0 |

## 分组结果

| 类别 | TripPilot成功 | Baseline成功 |
|---|---:|---:|
| A | 9/10 | 2/10 |
| B | 7/10 | 6/10 |
| C | 10/10 | 9/10 |
| D | 8/10 | 7/10 |
| E | 10/10 | 8/10 |

## Latency / Cost

| 指标 | TripPilot | Single-Agent |
|---|---:|---:|
| 平均延迟（秒） | 17.939 | 32.353 |
| 中位延迟（秒） | 15.579 | 28.189 |
| P95延迟（秒） | 34.848 | 66.7 |
| Agent步骤（ReAct计数） | 均值 2.96；总计 148；可用 50/50 | 均值 4.78；总计 239；可用 50/50 |
| 工具调用（Harness计数） | 均值 14.96；总计 748；可用 50/50 | 均值 8.16；总计 408；可用 50/50 |
| 外部调用尝试 | 均值 24.84；总计 1242；可用 50/50 | 均值 14.92；总计 746；可用 50/50 |
| Qwen调用 | 均值 3.98；总计 199；可用 50/50 | 均值 5.76；总计 288；可用 50/50 |
| 输入Token | 均值 23115.16；总计 1155758；可用 50/50 | 均值 22669.46；总计 1133473；可用 50/50 |
| 输出Token | 均值 655.96；总计 32798；可用 50/50 | 均值 1271.84；总计 63592；可用 50/50 |
| 总Token | 均值 23771.12；总计 1188556；可用 50/50 | 均值 23941.3；总计 1197065；可用 50/50 |
| API已报告Token合计 | 1,188,556 | 1,197,065 |
| usage缺失调用 | 0 | 0 |

## Failed cases

| 系统 | ID | 类别 | 失败原因 |
|---|---|---|---|
| trippilot | A08 | A | EXCESSIVE_TRAVEL |
| trippilot | B01 | B | BUDGET_EXHAUSTED, constraint:budget, BUDGET_EXCEEDED |
| trippilot | B06 | B | OPENING_TIME_CONFLICT |
| trippilot | B08 | B | OPENING_TIME_CONFLICT |
| trippilot | D01 | D | OPENING_TIME_CONFLICT |
| trippilot | D09 | D | OPENING_TIME_CONFLICT |
| baseline | A02 | A | MAX_STEPS, constraint:destinations, MISSING_DESTINATION, EMPTY_DAY |
| baseline | A03 | A | MAX_STEPS, constraint:destinations, MISSING_DESTINATION, EMPTY_DAY |
| baseline | A04 | A | MAX_STEPS, constraint:destinations, MISSING_DESTINATION, EMPTY_DAY |
| baseline | A05 | A | MAX_STEPS, constraint:destinations, MISSING_DESTINATION, EMPTY_DAY |
| baseline | A07 | A | MAX_STEPS, constraint:destinations, MISSING_DESTINATION, EMPTY_DAY |
| baseline | A08 | A | MAX_STEPS, constraint:destinations, MISSING_DESTINATION, EMPTY_DAY |
| baseline | A09 | A | MAX_STEPS, constraint:destinations, MISSING_DESTINATION, EMPTY_DAY |
| baseline | A10 | A | MAX_STEPS, constraint:destinations, MISSING_DESTINATION, EMPTY_DAY |
| baseline | B03 | B | MAX_STEPS |
| baseline | B05 | B | constraint:arrival_deadline, ARRIVAL_DEADLINE, OPENING_TIME_CONFLICT |
| baseline | B06 | B | OPENING_TIME_CONFLICT |
| baseline | B08 | B | OPENING_TIME_CONFLICT |
| baseline | C09 | C | MAX_STEPS, constraint:weather, WEATHER_RISK |
| baseline | D01 | D | INVALID_OUTPUT, constraint:destinations, constraint:days, constraint:start_date, constraint:budget, constraint:transport_mode, NO_ITINERARY, MISSING_REQUIRED_SECTION |
| baseline | D04 | D | EXCESSIVE_TRAVEL |
| baseline | D09 | D | OPENING_TIME_CONFLICT |
| baseline | E01 | E | INVALID_OUTPUT, constraint:destinations, constraint:days, constraint:start_date, constraint:budget, constraint:memory, NO_ITINERARY, MISSING_REQUIRED_SECTION |
| baseline | E10 | E | INVALID_OUTPUT, constraint:destinations, constraint:days, constraint:start_date, constraint:budget, constraint:memory_override, NO_ITINERARY, MISSING_REQUIRED_SECTION |

## Limitations

- 五类人工定义样本各10题，非随机总体抽样；每系统只运行一轮，无置信区间，不声称架构因果提升。
- Qwen为真实qwen-plus，temperature=0；高德/铁路/航空证据为固定Provider数据。真实高德与酒店由独立5例LIVE smoke验收。
- 两系统共享合同、装配、费用计算与工具；Baseline没有A2A专家分解、独立Critic、动态重规划。Prompt与执行策略也不同。
- Task Success允许正确拒绝明确不可满足约束；Constraint Satisfaction仍按原始标签逐项计数，不把冲突伪装成满足。默认Critic约束也参与任务成败，但不自动增添标签分母。
- C组雨天证据在第一次规划前提供；模型可能直接选择室内而不触发Critic失败。严格Replanning指标仍按原标签计分，不能把直接避险算重规划成功，也不能把其余案例一概解释成重规划执行失败；这不是10次行程完成后突发天气的恢复实验。
- Routing与重规划对Baseline为N/A。工具指标按每案例实际工具集合计算，再汇总micro P/R/F1，不以调用次数充当工具选择准确率。
- Unsupported Claim Rate仅覆盖定义的结构化来源/价格/库存/估计一致性检查，不等于所有自然语言断言都得到外部证实。
- 两系统共用偏好存取与优先级逻辑；偏好指标差异可能来自整次运行失败或有效约束未产出，不能当成独立记忆算法提升。
- Preference Adherence检查已加载结构化偏好与有效约束；住宿地铁可达性无证据仍未知。门到门接驳采用公开说明的市中心估计。
- Agent步骤为runtime记录的ReAct步骤合计，不是所有图节点访问数；工具/外部调用数采用Harness预算计数，缓存命中和调用前拒绝不等同于一次实际Provider执行。
- 延迟包含协议及模型等待，P95使用nearest-rank；Token仅用API返回usage，缺失显示unavailable，已知部分另存reported_tokens。百分比最多截断六位，精确计数优先。
- 通用修复前预检与两次中间运行共89个已落盘案例，额外已记录376次Qwen调用、API已报告2,196,933 Token（存在usage缺失；中止时尚未落盘的请求可能有额外消耗，未核对账单）。单独归档，不计入正式50+50，没有选择性替换结果；见development_runs.json。
- Rail与Flight为Dataset，不是实时库存；酒店是Amap POI，不提供实时房价、房态、预订。
