# Design

## Context
DayPlan.activities 本来是列表且 React 全量渲染。真实模式 default_selections 显式截成一个 POI，Planner prompt 也要求转场日一个活动；Local Travel 只取两个真实地标。WeatherRecord 已进入 GraphState/Critic，但 DayPlan 未携带天气，适配器丢弃夜温。当前原例 Supervisor LIVE 检查有 start_date 时成功，无法宣称复现历史阻塞。

## Goals / Non-Goals
**Goals:** 明确澄清、合理日程、来源可靠的天气、可读旅行界面和可观测演示模式。
**Non-Goals:** 不修改图、协议执行、Harness 预算、Memory、数据集标签或历史测评结果；不新增 Agent、预订或餐厅系统。

## Decisions
- 保留 days 命名；从明确文字补齐缺失的必要字段，日期+天数派生 end_date。API 返回 needs_clarification/missing_fields/questions；兼容旧 questions 标签。
- 不重新建活动契约：扩展现有 Activity，保留嵌套 poi 与 start/end，新增时段、预计耗时、前一段路线、来源、可选项和备注。Day 增加用餐休息缓冲与 weather。
- 按地理邻近筛选、用已有路线排序和组装；交通/开放/餐食/时间窗决定可行数量。慢游一般2项，紧凑一般3–4项，转场1–3；不足不编造。
- 本地研究扩大已有搜索候选，规划前准备实际相邻路线，遵守原工具与循环预算；Critic 复用有界 replanning。
- Weather 来自既有 get_weather。仅同日期同城市且证据非 stale 的 amap_live 可展示真实 forecast；模拟单独标明，未来无预报不显示温度。最小兼容字段映射不改变 Provider 实现方式。
- 前端模式仅切换展示，协议/provider 状态仍取实际运行；技术详情默认折叠。警示复用 Critic WEATHER_RISK，不另写天气判断。
- 两天内范围：先数据与规则/测试，再前端/真实浏览器/LIVE验收与文档。

## Risks / Trade-offs
更多 POI 增加路线成本，受原有预算限制；不足须报告部分完成。天气仅覆盖高德实际预报期，未来旅行日期待确认。日程规则会改变新运行结果，因此历史50-case结果保留原样、不将旧数字冒充新版本成绩；可选新测评单独保存。
