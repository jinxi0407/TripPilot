# 最终简历声明核验

日期：2026-09-22。针对本次用户提供的最终文案，不覆盖[此前原文审计](resume-claim-audit.md)。统计按 **4 条职责 + 2 条成果 + 22 项能力 = 28 条**，下表每行只计一次。

**SUPPORTED：28；PARTIAL：0；NOT SUPPORTED：0。**

SUPPORTED 指有实现及对应证据，并受文中数据边界约束；不表示每次真实行程都能满足全部约束。证据包括未改写的正式评测、本轮完整回归和[本轮 LIVE 实测](final-clean-live-check.json)。

## 六条最终文案

| 编号 | 最终声明 | 判定 | 依据与边界 |
| --- | --- | --- | --- |
| R1 | LangGraph 五 Agent 协作，通过 A2A 分发与回传 | SUPPORTED | [工作流](../backend/app/graph/workflow.py)、[A2A client](../backend/app/a2a/client.py)、[两个专家服务](../backend/app/a2a/service.py)。五个逻辑 Agent，两个独立 A2A 服务，Supervisor 依次委派。 |
| R2 | MCP 接入交通、景点、酒店、天气及路线，结合 Qwen / 高德支持比较、住宿、地图和多城市规划 | SUPPORTED | [7 个工具合同](../backend/app/mcp/schemas.py)、[交通比较](../backend/app/services/transport_comparison.py)、[住宿](../backend/app/services/accommodation.py)、[地图](../frontend/src/components/LiveMap.tsx)。本轮真实 Qwen / Amap 已调用；铁路/航班 DATASET，酒店为 Amap POI，无实时房价和库存。 |
| R3 | 受控 ReAct + Critic，仅确认冲突触发重规划，保护超时、重复调用与异常降级 | SUPPORTED | [Planner](../backend/app/agents/planner.py)、[Critic](../backend/app/agents/critic.py)、[Harness](../backend/app/harness/runtime.py)、[语义回归](../backend/tests/test_validation_semantics.py)。confirmed + blocking 是触发条件；有限尝试不保证修复成功。本轮交通超时冲突在有界尝试后如实保留。 |
| R4 | Session / 长期偏好记忆，50 个固定任务评估规划和工具调用，独立故障注入及回归验证恢复/降级 | SUPPORTED | [记忆实现](../backend/app/persistence/memory.py)、[固定 50 题](../evals/v1_2/benchmark_50.jsonl)、[10 个独立故障场景](../evals/v1_2/failure_results.json)、[Harness 测试](../backend/tests/test_harness.py)。不把主评测与故障评测混为一谈。 |
| R5 | 历史 88%→最终 96%（48/50），同模型 Baseline 64%（32/50）；结合 Demo 与回归统一校验语义 | SUPPORTED | [历史结果](../evals/v1_2/summary.md)、[最终结果](../evals/v1_2_2/summary.md)、[语义定义](../evals/v1_2_2/semantics.md)。本轮离线重新汇总原始结果，数字一致、文件不变。单次内部评测的版本差异，不作统计显著性或单项修复因果声明。 |
| R6 | 215 后端、24 浏览器测试，Qwen / 高德 / MCP / A2A 真实联调，本地端到端落地 | SUPPORTED | [最终代码审计](final-code-audit.md)、[本轮 LIVE 实测](final-clean-live-check.json)。215/215、24/24，另有前端单元 1/1。本轮两个实际场景均执行完整协议链；五天案例保留确认交通冲突，三天交通比较案例为 partial、无确认阻塞。自动化 Mock 回归与真实 API 验收分别记录。 |

## 22 项能力保留检查

| 编号 | 能力 | 判定 | 实现 / 验证 |
| --- | --- | --- | --- |
| C1 | LangGraph Multi-Agent | SUPPORTED | [graph/workflow.py](../backend/app/graph/workflow.py)；后端哈希未变。 |
| C2 | Supervisor Agent | SUPPORTED | [supervisor.py](../backend/app/agents/supervisor.py)。 |
| C3 | Transport Agent | SUPPORTED | [transport.py](../backend/app/agents/transport.py)；本轮 A2A ONLINE。 |
| C4 | Local Travel Agent | SUPPORTED | [local_travel.py](../backend/app/agents/local_travel.py)；本轮 A2A ONLINE。 |
| C5 | Travel Planner | SUPPORTED | [planner.py](../backend/app/agents/planner.py)；本轮完成真实规划。 |
| C6 | Critic | SUPPORTED | [critic.py](../backend/app/agents/critic.py)；本轮区分 confirmed / unverified / informational。 |
| C7 | A2A | SUPPORTED | [service.py](../backend/app/a2a/service.py)；两个专家服务与 Agent Cards。 |
| C8 | MCP | SUPPORTED | [schemas.py](../backend/app/mcp/schemas.py)；search_rail、search_flights、search_poi、search_hotels、get_weather、calculate_distance、plan_route。 |
| C9 | ReAct | SUPPORTED | [planner.py](../backend/app/agents/planner.py) 的结构化 Action / Observation 循环。 |
| C10 | Runtime Harness | SUPPORTED | [runtime.py](../backend/app/harness/runtime.py)、[policy.py](../backend/app/harness/policy.py)；预算、重试、超时、重复调用和降级测试通过。 |
| C11 | Session Memory | SUPPORTED | [memory.py](../backend/app/persistence/memory.py)、[test_memory.py](../backend/tests/test_memory.py)；会话在内存中，重启清空。 |
| C12 | SQLite Preference Memory | SUPPORTED | 同上；只持久化用户明确选择保存的结构化偏好，本轮 LIVE 检查未改写用户偏好。 |
| C13 | Qwen | SUPPORTED | [model_client.py](../backend/app/services/model_client.py)；本轮 qwen-plus LIVE。 |
| C14 | Amap | SUPPORTED | [amap.py](../backend/app/providers/amap.py)、[LiveMap.tsx](../frontend/src/components/LiveMap.tsx)；真实服务及底图，长名称裁切修正后桌面/手机逐日视野 10/10 通过，原始失败与后续复验分别保留。 |
| C15 | FastAPI | SUPPORTED | [main.py](../backend/app/main.py)；健康、规划、地图代理与偏好接口保留。 |
| C16 | 50-case Benchmark | SUPPORTED | [benchmark_50.jsonl](../evals/v1_2/benchmark_50.jsonl)；50 个唯一任务、5 类各 10 个。 |
| C17 | Single-Agent Baseline | SUPPORTED | [single_agent.py](../evals/baseline/single_agent.py)；同模型、共用数据/合同/确定性装配，无专家分解与独立 Critic。 |
| C18 | Hotel Recommendation | SUPPORTED | [hotel.py](../backend/app/providers/hotel.py)、[accommodation.py](../backend/app/services/accommodation.py)；候选来源 amap_live，价格/房态仍未知。 |
| C19 | Rail / Flight Comparison | SUPPORTED | [transport_comparison.py](../backend/app/services/transport_comparison.py)；本轮北京→上海真实工作流展示两类 DATASET 候选与门到门估算。 |
| C20 | Dynamic Replanning | SUPPORTED | [workflow.py](../backend/app/graph/workflow.py)、[Critic](../backend/app/agents/critic.py)；本轮实际发生 1 次有界重规划，未解决时停止并保留冲突。 |
| C21 | 自动化测试 | SUPPORTED | [backend/tests](../backend/tests/)、[frontend/unit](../frontend/unit/)；215 后端 + 1 前端单元全部通过。 |
| C22 | Browser tests | SUPPORTED | [frontend/tests](../frontend/tests/)；24 项全部通过，包括地图、天气、记忆、窄屏、故障与校验 UI。 |

## 面试时应保留的限定

- 96% 是固定任务、固定 Provider 数据、真实 Qwen 的项目内部单次评测，不代表任意实时旅行需求的成功率。
- 本轮实时五天案例发现市内交通 123 分钟超过 120 分钟限制，重规划后仍有冲突。这证明受控退出存在，也说明不能宣称 LIVE Demo 永远无冲突。
- 开放时间、未来天气、酒店价格与房态不足时保留待确认；“工具 LIVE”不等于所有旅行事实都已验证。
- Session 是进程内会话；SQLite 是本地结构化偏好。两个 A2A 服务不等于五个独立部署服务。
- 清理未改变核心行为，没有重新消耗 50+50 Qwen 评测，也没有重写历史验收结果。
