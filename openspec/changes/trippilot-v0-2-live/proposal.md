# Proposal

## Why
V0.1 已完成 Mock Demo，但真实模型、地图服务与浏览器底图尚未端到端联调。用户已授权使用本地凭据完成 V0.2 实现与真实请求验证。

## What Changes
- 验证 Qwen 与高德 Web Service，修复真实响应的合同问题，保留原有 Mock。
- 增加按实际执行结果展示的 Provider 状态，以及当天 POI 的真实高德底图与 Marker。
- 支持实时模型/地图数据与 Dataset 铁路混合运行，暴雨模拟单独标记，禁止冒充真实天气。
- 回归测试隔离本地凭据，记录真实联调证据和未完成事项。

## Capabilities
### New Capabilities
- `live-integration`: 真实服务接入、运行状态、浏览器地图及联调验证。
### Modified Capabilities
无已归档主规格变更；沿用 V0.1 五 Agent 和有界执行设计。

## Impact
Backend providers/services/API、React 地图和状态、离线测试与联调文档。无新 Agent、框架、铁路爬虫、commit 或 push。
