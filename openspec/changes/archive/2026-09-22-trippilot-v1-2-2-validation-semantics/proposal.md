# Proposal

## Why
当前 validation 同时表达证据缺口与已确认冲突，中文提示混淆两者，且重规划按旧严重程度/类型触发，旅行模式展示逐活动重复提示。本轮修正语义并重新测量版本表现。

## What Changes
三类 Issue 契约、已确认硬冲突 blocking gate、事实/估算预算区分、天气/开放时间/交通/酒店未知的独立消息、去重与前端聚合、版本化评测与严格重规划指标。

## Capabilities
### New Capabilities
- `validation-semantics`: 有证据的冲突、待确认与信息提示的端到端语义。
### Modified Capabilities
无。

## Impact
仅 schema、Critic/费用汇总/必要证据关联、UI、测试、版本化 evaluator。保留五Agent、LangGraph拓扑、MCP/A2A协议、Harness策略、Memory及Provider架构。原50-case、labels与结果文件不修改。无提交、推送或合并。
