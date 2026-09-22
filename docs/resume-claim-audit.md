# 简历声明核验

核验日期：2026-09-22。范围为当前 V1.2.2 本地作品集版本，依据源代码、正式原始评测、已有 LIVE 验收和本轮完整回归。未改写结果、案例、标签或核心行为，也未再次调用模型运行 50+50 Benchmark。

判定：SUPPORTED 表示在注明的范围内有实现与验证依据；PARTIALLY_SUPPORTED 表示部分事实成立但原句需要收紧；NOT_SUPPORTED 表示没有足够证据。下列统计按 **9 条原简历声明 + 17 条专项检查 = 26 条**计数，不重复计算子项。

**SUPPORTED：24；PARTIALLY_SUPPORTED：2；NOT_SUPPORTED：0。** 发布推荐文案采用下文修订后的两句话，保留原声明的核验结果，不把原文中的部分支持隐藏为全部支持。

## 原简历逐条核验

| 编号 | 原声明 | 判定 | 实际情况与证据 |
| --- | --- | --- | --- |
| R1 | TripPilot｜多智能体 AI 旅行规划平台 | SUPPORTED | 五个逻辑 Agent，见 [LangGraph 工作流](../backend/app/graph/workflow.py)。范围为本地工程化 Demo。 |
| R2 | LangGraph、ReAct、MCP、A2A、Qwen、Amap、FastAPI、React、SQLite | SUPPORTED | [Python 依赖](../backend/requirements.txt)、[前端依赖](../frontend/package.json)、[Planner](../backend/app/agents/planner.py)、[协议](../backend/app/services/protocols.py)、[SQLite 偏好](../backend/app/persistence/memory.py)，均有实际调用而非空接口命名。 |
| R3 | 面向多城市信息分散和单 Agent 复杂约束规划稳定性问题，根据日期、预算、偏好生成并调整行程 | SUPPORTED | 项目目标与 [Supervisor](../backend/app/agents/supervisor.py)、[修订 API](../backend/app/api/plans.py)、[固定任务结果](../evals/v1_2_2/summary.md) 一致。稳定性比较仅限本项目内部评测，不推广为所有单 Agent 系统的普遍结论。 |
| R4 | 基于 LangGraph 的 Supervisor、Transport、Local Travel、Travel Planner、Critic，通过 A2A 分发与回传 | SUPPORTED | [工作流](../backend/app/graph/workflow.py)、[A2A client](../backend/app/a2a/client.py)、[独立服务](../backend/app/a2a/service.py)、[协议集成测试](../backend/tests/test_protocols.py)。两个专家服务由主进程委派，并非五个 Agent 都是独立网络服务。 |
| R5 | MCP 接入高铁、航班、POI、酒店、天气、路线，结合 Qwen 与高德真实 API 支持比较、住宿、地图和规划 | SUPPORTED | [7 个工具合同](../backend/app/mcp/schemas.py)、[交通比较](../backend/app/services/transport_comparison.py)、[住宿](../backend/app/services/accommodation.py)、[真实地图](../frontend/src/components/LiveMap.tsx)、[LIVE 报告](v1.2.2-validation-report.md)。这里的“真实 API”仅指 Qwen / 高德；铁路与航班为 DATASET，酒店无实时价格/库存。 |
| R6 | 受控 ReAct + Critic，仅确认冲突触发动态重规划，保护超时、重复调用和异常降级 | SUPPORTED | [Planner action/observation 循环](../backend/app/agents/planner.py)、[Critic](../backend/app/agents/critic.py)、[issue schema](../backend/app/schemas/travel.py)、[Harness](../backend/app/harness/runtime.py)、[语义测试](../backend/tests/test_validation_semantics.py)、[边界测试](../backend/tests/test_harness.py)。confirmed 且 blocking 才触发；有界尝试不保证一定修复成功。 |
| R7 | Session / 长期偏好记忆，50-case Benchmark 评估规划、工具调用和故障恢复 | PARTIALLY_SUPPORTED | [Memory](../backend/app/persistence/memory.py) 与 [50 个固定任务](../evals/v1_2/benchmark_50.jsonl) 成立；故障恢复另由 [10 个受控注入场景](../evals/v1_2/failure_results.json) 及 [Harness 测试](../backend/tests/test_harness.py) 验证，不能说 50 个主任务直接等于故障恢复评测。 |
| R8 | 成功率 88%→96%（48/50），Baseline 64%（32/50）；通过评测修复 Critic 将待验证误判为真实冲突 | PARTIALLY_SUPPORTED | [V1.2 原始结果](../evals/v1_2/results_tripilot.jsonl)、[V1.2.2 TripPilot](../evals/v1_2_2/results_tripilot.jsonl) / [Baseline](../evals/v1_2_2/results_baseline.jsonl) 支持数字；[真实 before/after](v122-before-after.json) 的 before 已是 partial、0 confirmed，未复现错误自动重规划。修复包括语义契约、未知信息文案/UI 和潜在错误分支，后者有回归测试；不能把增长单因归于 Critic。 |
| R9 | 215 后端、24 浏览器测试，Qwen / 高德 / MCP / A2A 全链路真实联调、本地端到端落地 | SUPPORTED | [本轮发布回归](portfolio-release-report.md) 实测 215/215、24/24，另有 1 项前端单元测试；[真实 backend 结果](v122-live-after.json)、[浏览器真实地图验收](v122-browser-validation.json)。自动化回归隔离外部 API，LIVE 是独立验收证据，不代表 215 个测试都用真实付费接口。 |

## A–Q 专项检查

| 项 | 判定 | 可定位的实现 / 验证证据 |
| --- | --- | --- |
| A：五个 Agent | SUPPORTED | [workflow.py / build_graph](../backend/app/graph/workflow.py) 注册 supervisor、transport、local、planner、critic；对应 `backend/app/agents/` 五个文件。 |
| B：两个独立 A2A Service | SUPPORTED | [service.py](../backend/app/a2a/service.py) 的 transport_app / local_app；[启动器](../scripts/dev_v1_1.py) 的两个子进程；[test_supervisor_real_a2a_tasks_mcp_artifacts_and_graph](../backend/tests/test_protocols.py)。 |
| C：MCP 实际暴露 7 tools | SUPPORTED | [server.py](../backend/app/mcp/server.py) 注册合同；[test_v12_seven_tools_hotels_flights_real_protocol](../backend/tests/test_protocols.py) 使用真实本地 HTTP discovery/call。旧测试函数名保留 five_tools，但断言对比的是现有完整 CONTRACTS，不以名字判断数量。 |
| D：七个指定工具名 | SUPPORTED | [CONTRACTS](../backend/app/mcp/schemas.py)：search_rail、search_flights、search_poi、search_hotels、get_weather、calculate_distance、plan_route。 |
| E：Qwen LIVE | SUPPORTED | [QwenClient](../backend/app/services/model_client.py)、[正式运行 manifest](../evals/v1_2_2/manifest.json)、[100 条 LIVE 模型证据核验](v122-benchmark-integrity.json)，模型 qwen-plus。 |
| F：高德 Web Service / JS Map LIVE | SUPPORTED | [AmapProvider](../backend/app/providers/amap.py)、[地图代理](../backend/app/api/maps.py)、[LiveMap](../frontend/src/components/LiveMap.tsx)、[V0.2 接口验收](v0.2-live-report.md)、[V1.2.2 浏览器验收](v122-browser-validation.json)。未来日期无预报仍待确认。 |
| G：真实 Action / Observation loop | SUPPORTED | [plan / PlannerDecision](../backend/app/agents/planner.py)：逐步读取 action、调用工具、累积 Observation 并再次决策；结构化 final 终止。Fixture 另用确定性模型，不能代替 LIVE 模型证明。 |
| H：confirmed + blocking gate | SUPPORTED | [CriticIssue](../backend/app/schemas/travel.py) 不变量：blocking 必须 confirmed/error；[critique](../backend/app/agents/critic.py) 仅收集 blocking 问题；[test_nonconfirmed_issue_cannot_block](../backend/tests/test_validation_semantics.py) 及未知开放/天气/预算测试。 |
| I：Harness 七项保护 | SUPPORTED | [runtime.py](../backend/app/harness/runtime.py)、[budget.py](../backend/app/harness/budget.py)、[policy.py](../backend/app/harness/policy.py)：step limit、timeout、retry、whitelist、duplicate detection、fallback、structured validation；[test_harness.py](../backend/tests/test_harness.py) 分别验证上限、取消、重试、拒绝与受控降级。 |
| J：Session Memory | SUPPORTED | [SessionMemory / SessionStore](../backend/app/persistence/memory.py)、[RunService](../backend/app/services/runs.py)、[test_session_continuation_retains_itinerary_constraints](../backend/tests/test_memory.py)；内存会话，重启清空。 |
| K：SQLite 长期偏好 | SUPPORTED | [PreferenceStore](../backend/app/persistence/memory.py)、[test_preferences_save_load_update_clear](../backend/tests/test_memory.py)；只存结构化偏好，用户未开启记忆不写入。 |
| L：恰好 50 个固定任务 | SUPPORTED | [benchmark_50.jsonl](../evals/v1_2/benchmark_50.jsonl)、[load_cases](../evals/v1_2/schema.py)、[test_exact_fifty_reviewed_cases_and_no_label_in_request](../backend/tests/test_benchmark_v12.py)；V1.2.2 复用原文件，不复制题目。 |
| M：48/50 | SUPPORTED | [V1.2.2 TripPilot 原始 50 行](../evals/v1_2_2/results_tripilot.jsonl)、[summary](../evals/v1_2_2/summary.json)，失败 B01/B02 保留。 |
| N：32/50 | SUPPORTED | [V1.2.2 Baseline 原始 50 行](../evals/v1_2_2/results_baseline.jsonl)、[summary](../evals/v1_2_2/summary.json)，18 个失败案例未删除。 |
| O：历史 44/50 | SUPPORTED | [V1.2 原始 50 行](../evals/v1_2/results_tripilot.jsonl)、[历史 summary](../evals/v1_2/summary.json)。 |
| P：215 backend tests | SUPPORTED | 本轮完整 pytest：215 passed、0 failed；第三方 anyio/Starlette 有 1 条弃用警告。[发布报告](portfolio-release-report.md)。 |
| Q：24 browser tests | SUPPORTED | 本轮 Playwright：24 passed、0 failed。[发布报告](portfolio-release-report.md)，包括天气、窄屏、未知信息与确认冲突呈现。 |

## 必须修改的两句

**职责 4 原句：** “实现 Session Memory 与长期旅行偏好记忆，并建立 50-case Agent Benchmark，持续评估规划质量、工具调用和故障恢复能力并迭代系统。”

**推荐：** “实现 Session Memory 与 SQLite 长期旅行偏好记忆；建立 50 个固定任务的 Agent Benchmark 评估规划质量与工具调用，并通过独立故障注入场景和回归测试验证运行保护及降级能力。”

**成果 1 原句：** “Benchmark 迭代过程中任务成功率由 88% 提升至 96%（48/50），同模型 Single-Agent Baseline 为 64%（32/50）；通过评测定位并修复 Critic 将‘待验证信息’误判为真实约束冲突的问题。”

**推荐：** “在项目内部 50 个固定任务评测中，V1.2.2 任务成功率为 96%（48/50），历史 V1.2 为 88%（44/50），同模型 Single-Agent Baseline 为 64%（32/50）；结合真实 Demo 与回归测试，统一 Critic 的确认冲突、待验证信息与提示语义，仅由 confirmed + blocking 问题触发有界重规划。”

两句修订文案均为 SUPPORTED；其余简历条目在本地 Demo、Rail/Flight DATASET、Hotel POI 的明确范围内成立。可在职责 2 后增加“铁路/航班采用固定数据集，酒店为 POI 推荐”，避免读者理解成实时余票与酒店预订。

## 不能扩大解释的结论

- 88%→96% 是两个版本各一次执行的观察差异。期间包含 V1.2.1 产品修复、V1.2.2 语义变化和模型服务波动，没有消融或统计显著性证明。
- 旧重规划分母为 10 个预标注天气任务；新严格口径为 3 个真实观察到确认冲突的任务，修复 1 个。不能将 1/10→1/3 说成恢复能力提升。
- 真实 before 为 partial、0 confirmed；修复后的 18 条待验证信息、2 条提示、0 条确认冲突不等于“所有旅行事实已验证”。
- 自动化测试、受控故障注入、固定 Provider 的 LIVE 模型评测、真实高德浏览器验收是四类不同证据，不能互相替代。
- 本轮只通过校验和、schema、结果计数及 evaluator 回归核对已有评测。LIVE 状态引用已完成验收，不额外声称重新执行了全套付费 API 联调。
