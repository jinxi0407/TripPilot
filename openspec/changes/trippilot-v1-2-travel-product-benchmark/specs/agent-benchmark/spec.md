## Purpose
建立可复现且公平的旅行智能体测量流程，以固定任务、共同事实证据和结构化评估比较多智能体与单智能体架构，另行记录运行故障和真实服务联调，不用预设答案伪造能力提升。

## ADDED Requirements

### Requirement: Fixed reviewed fifty cases
Benchmark SHALL 恰好50题，五类别各10题，具有完整标签、可选多轮输入、目的地、硬软约束、路由/工具期望和功能需求；标签仅供evaluator，生产代码不可读取expected字段或case IDs。
#### Scenario: Dataset validation
- **WHEN** 运行前校验数据集
- **THEN** 验证50唯一ID、10/10/10/10/10分布、schema与标注一致性，保存固定数据指纹，错误不启动计费运行。

### Requirement: Fair reproducible baseline
双方 SHALL 使用相同50题、qwen-plus、temperature0、固定Rail/Flight/高德fixture、工具合同和evaluator。Baseline SHALL 无A2A拆解、独立Critic或动态重规划，但可用同样工具；不修改生产LIVE逻辑。
#### Scenario: Comparable runs
- **WHEN** 执行两个架构
- **THEN** 保留模型/数据/配置/代码指纹及同一用户输入，不向任一方提供预期答案，比较率差自动计算为百分点。

### Requirement: Objective complete metrics
Evaluator SHALL 计算Task Success、hard constraint满足、路由、工具Exact/Precision/Recall/F1、重规划、偏好/覆盖、住宿、交通和无依据声明率，以及真实latency/steps/calls/API tokens；缺失usage显示unavailable，无适用样本为N/A。
#### Scenario: Correct impossible constraint
- **WHEN** 200元五天三城被明确拒绝
- **THEN** 可计任务成功而不伪造费用合规；假成功方案算失败，所有失败ID/类别/原因列出。
#### Scenario: Honest report
- **WHEN** 结果指标较低或部分失败
- **THEN** summary和resume_metrics保留真实分子分母、限制及完整失败列表，不调整标签或隐藏失败。

### Requirement: Durable bounded execution
Runner SHALL 逐例保存、支持resume、每例timeout、每5例安全进度、并发不超过2，限制单例/总体模型调用、步数和运行时长。达到上限 SHALL 保存partial并停止新case。
#### Scenario: Interrupted run
- **WHEN** 中断后恢复
- **THEN** 已完成结果不丢失不重复付费，配置/数据不一致时拒绝混合结果。

### Requirement: Separate failures and live smoke
系统 SHALL 额外执行10种指定故障并区分检测、恢复、fallback和安全失败；主Benchmark之后运行5例真实Qwen/高德酒店/MCP/A2A smoke并报告真实成功数。
#### Scenario: Fault accounting
- **WHEN** 注入MCP离线/超时、两A2A离线、高德超时、Qwen瞬时失败、无效结构、重复循环、工具预算或越权
- **THEN** 记录Detection/Graceful Recovery/Fallback Success及原因，安全拒绝不伪装完成行程。
#### Scenario: Deliverables and regression
- **WHEN** 验收结束
- **THEN** 提供benchmark_50.jsonl、两results JSONL、summary JSON/Markdown、resume_metrics、故障和5例LIVE证据，运行全部回归/浏览器/Ruff/build/strict，停止功能开发且不push/merge。
