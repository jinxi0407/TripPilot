# Proposal

## Why
V1.2 的真实景点被保守策略压缩为每天一项，天气止于内部状态，技术信息抢占旅行内容。需要完善有证据的日程和信息层级，并消除澄清提示不明确的问题。

## What Changes
- 核查澄清链路，只由出发地、目的地、日期和天数阻塞；派生结束日期并返回明确字段与问题。
- 基于现有 POI、路线和时间窗丰富日程；加入轻量 Day Quality 检查。
- Day weather 和 Activity 展示字段做向后兼容补充。
- 默认旅行模式、可切换演示模式、紧凑偏好、摘要、日程与天气、住宿和交通折叠详情。

## Capabilities
### New Capabilities
- `product-polish`: 可读、合理、有来源的旅行产品界面与日程质量。
### Modified Capabilities
无。

## Impact
限 Supervisor、Local Travel 查询策略、Planner 选点与组装、Critic 检查、兼容 schema 和 React 展示。Amap 仅补充原始返回的天气字段映射。禁止协议、Provider 架构、Harness、Memory 和 Benchmark 重构；不新增 Agent 或框架，不提交或推送。
