# Design

## Context
见 proposal.md。根目录 .env 已由 Pydantic Settings 和 Vite envDir 读取；不复制凭据。V0.1 的铁路 Dataset 日期固定，真实预报仅覆盖短期，因此完整五天输出可能合法地为 partial。

## Goals / Non-Goals
保留五 Agent、Schema、Registry、8 步和两次重规划上限。仅对真实集成必要部分做增量修改；不扩展订票、认证或新的框架。

## Decisions
- Provider 在真实调用成功后报告 LIVE；配置齐全只报告 PENDING。失败报告 FAILED，只有实际 Mock 才报告 MOCK，避免错误标记。
- 模型环境变量以 QWEN_CHAT_MODEL 为首选，QWEN_MODEL 仅兼容回退；内部仍使用单一 qwen_model 字段。非空首选名称优先于旧名称，同名配置按进程环境、根目录 .env 顺序读取；DASHSCOPE_BASE_URL 沿用原有加载方式。
- Qwen 关闭思考模式、校验结构化 JSON，保留真实返回模型名与安全错误，不记录原始响应。若配置 DashScope 原生 `/api/v1` 根路径，则在原账户区域主机内转换到 `/compatible-mode/v1`，不更换账户区域。
- 高德来源使用 source=amap_live，source_kind=live 保持现有合同；数值错误码可安全展示。
- 地图按官方 serviceHost 方式经现有 FastAPI 转发白名单地图请求并附加 securityJsCode，避免把安全码编入前端。浏览器 JS Key 为 SDK 必要配置，不输出到日志。SDK 初始化 JSONP 仅在回调合法且响应匹配时使用 JavaScript MIME，保留 nosniff；Marker 标签将经 textContent 转义的名称序列化为 SDK 所需的 HTML 字符串。
- 日期使用现有 Dataset Demo 日期，不移动或伪造真实预报；暴雨修订增加显式模拟证据，POI/路线继续真实查询。
- 离线测试隔离 .env 与外部网络；真实检查独立、显式运行。工作按配置、API、地图、完整场景、回归顺序，保持两天 Demo 的规模。

## Risks / Trade-offs
- [缺少模型名或地图安全码] → 报告缺失，继续不依赖它们的工作，等待用户本地补充。
- [API 配额、同名 POI、预报覆盖不足] → 原始安全错误码、限定地点搜索、未知信息保留 partial。
- [浏览器请求包含 JS Key] → 不收集 HAR/原始网络日志，后端访问日志移除查询字符串。
- [真实票价/开放时间缺失] → 保持未知，禁止把通过流程等同于全部约束已证实。

## Migration Plan
重启现有本地前后端加载配置，离线与真实验收分别执行。显式 fixture 模式保留原 Demo；回退仅切换用户选择的模式，不改写凭据或隐式冒充 LIVE。
