# V1.2.2 评测语义迁移

原始50题仍从 `evals/v1_2/benchmark_50.jsonl` 读取，不复制、不改写案例或标签。V1.2.2 runner、evaluator、结果与报告独立存放；V1.2 目录及 Single-Agent 实现保持原样。模型、temperature、固定 Provider、每题及全局限额沿用 V1.2。

## 不变的判定

- Hard constraints、required tools、routing、memory、hotel、unsupported claims 的 ground truth 不变。
- Budget 硬约束仍使用原始费用完整性与估算总额判定；`BUDGET_RISK` 不阻断产品，并不自动让 Benchmark 的预算约束通过。
- 正确的不可满足拒绝仍需案例允许失败、实际 `conflict` 和已确认问题，不把未知事实包装成正确拒绝。
- Single-Agent 仍使用原实现，不加入 Critic 或专家分解；双方使用共享类型合同、行程装配、费用计算。

## Issue schema 兼容

旧 `severity == high` 改为新 `blocking == true`。否则换了 schema 后 evaluator 会看不到所有真实冲突，造成虚假成功。

城际可行性增加新 `TRANSPORT_CONFLICT` 的识别，同时明确要求跨城日存在铁路或航班证据。产品允许 `TRANSPORT_UNVERIFIED` 返回 partial，不等于评测已经证明可行。

## Replanning：旧定义

仅对标签 `requires_replanning=true` 的10个天气案例计分：Trace 存在失败的 Critic、重规划次数大于0、最终天气硬约束满足且无运行失败。无论是否实际发生了天气冲突都进入分母。提前选择室内活动也会被计为失败；其他类型冲突触发的重规划可能被误当作天气修复。

V1.2.2 同时输出 `legacy_replanning_success` 以保留这一定义的当前结果。

## Replanning：新严格定义

使用实际 Critic 的有界 `validation_history`，每个案例至多保留原有最大重规划次数+1次校验：

1. 必须有实际已确认的 blocking 问题，才进入机会分母；只含未知信息或提前避开冲突为 N/A。
2. 必须由 Critic 请求重规划；出现确认冲突但由于上限等原因没有修复不能排除，计失败。
3. 必须有后续 Critic 校验证明原目标冲突已消除，且最终不存在任何 blocking 问题；运行失败也不能算修复成功。
4. 按案例计分，一个案例多个问题需全部修复，不能只挑成功的问题。
5. 分母覆盖所有实际确认冲突（含预算、时间、天气、酒店等），不局限于天气标签。Baseline 没有 Critic→replan 闭环，指标为 N/A。

因此新分数不能与历史1/10直接解释为性能提升。案例标签没有变更；变化的是从执行历史定义可观测的重规划机会。正式报告同时列出新分母的案例和失败原因。

## 历史测试

V0.1 fixture 测试保留旧案例文件和标签，通过显式 alias 断言新的类型：旧开放时间、天气、预算未知和换乘名称映射到新契约。单纯路线优化提示不再要求自动重规划，但仍要求该提示存在、执行有界、状态正确且交通没有编造。该兼容只存在测试中，不进入正式50题 ground truth。

## 可比性限制

这是一次新的真实 Qwen 执行，并非旧结果重算。V1.2.1 没有正式 Benchmark；V1.2 到 V1.2.2 之间还包含活动密度、天气UI及装配保护等已授权改动，加上模型服务波动，不能把差异全部归因于 Critic schema。
