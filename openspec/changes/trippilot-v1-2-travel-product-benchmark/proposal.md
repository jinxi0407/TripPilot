# Proposal

## Why
V1.1 已有真实协议、运行控制和 LIVE 证据，但尚不能延续用户偏好、结合行程推荐住宿或比较铁路与航空。V1.2 补齐这些有限产品能力，并用固定50题、公平单智能体基线与独立故障集测量架构效果，之后停止扩展功能。

## What Changes
- Session Store 延续当前行程、约束、修订、交通和住宿选择；SQLite 仅持久化结构化偏好，支持 opt-in、更新和清除，优先级为当前请求 > 会话 > 长期偏好。
- Local Travel 复用现有高德请求层查询 Hotel POI；结合每日景点、路线、车站和偏好推荐区域与候选，Critic 检查过远/绕路/车站接驳，并最多一次住宿重选且计入全局重规划。
- Transport 增加 DatasetFlightProvider 与授权 Real 接口；比较含接驳和缓冲的门到门估计，保留未知值与来源，不声称实时库存。
- MCP 扩为7个工具，A2A 仍为两个专家服务，现有 Harness / ReAct / Critic 保持；前端增量展示偏好、住宿与交通比较以及实际状态。
- 50个经人工式逐条审核的固定任务（五类各10）；同 qwen-plus、temperature=0、数据、工具与 evaluator 的 Single-Agent Baseline；结果逐题落盘、可恢复、有总预算；额外10项故障与5项 LIVE smoke。
- 保留所有旧 change 和检查点，不增加 Agent、爬虫、购买/订票、登录、向量库、队列或新协议；不 push/merge，不保存完整聊天到长期数据库。

## Capabilities
### New Capabilities
- `travel-memory-product`: 会话与长期偏好、酒店与航班、行程相关推荐、7工具协议及 UI。
- `agent-benchmark`: 固定任务、客观评估、公平基线、安全执行、故障与 LIVE smoke 证据。
### Modified Capabilities
无已归档主规格；V1.1 change 历史不修改，本 change 明确替代运行时5工具数量要求为7。

## Impact
增量修改 backend 的 schema、persistence、Provider、Registry、现有专家/图、API；扩展现有 React 组件和 evals。SQLite 使用 Python 标准库，无新增业务框架。V1.1 checkpoint b66dc59，V0.2 209918f 均保留；当前分支 feat/v1.2-travel-product-benchmark。
