# Proposal

## Why
V0.2 已验证真实模型与地图，但专家和工具仍在同一进程内调用，运行保护散落在 Registry、模型客户端和 Agent 中。V1.1 用真实标准协议与统一运行控制展示可验证的 Agent 工程能力，同时保留现有 Demo。

## What Changes
- 固定官方稳定 MCP 2.2.0 与 a2a-sdk 1.1.5；独立 MCP Streamable HTTP 服务复用现有五类 Provider。
- 两个独立 A2A 专家服务提供 Agent Cards，通过标准消息和结构化任务产物返回现有 LangGraph 状态。
- 统一 Harness 策略、调用与步骤预算、重试、超时、权限、重复保护、schema 校验与安全摘要。
- 实际 runtime health、协议执行链和明确 fallback 状态进入 API 与前端；统一开发启动脚本。
- 增加真实本地协议集成、Harness 故障、现有回归和四个 LIVE 场景验收。

## Capabilities
### New Capabilities
- `agent-protocol-runtime`: MCP/A2A 真协议执行、Harness 控制、可观测性、降级及兼容验收。
### Modified Capabilities
无已归档主规格；V0.1/V0.2 change 保持原样。

## Impact
Backend 增加 mcp/a2a/harness 模块并增量连接现有 graph/services/providers；API 增加 runtime 字段；React 增加状态展示；依赖锁定、scripts 与 docs 更新。不增加逻辑 Agent、数据库、队列、认证、订票或爬虫。已按用户授权完成本地 checkpoint；后续不 push、不 merge。
