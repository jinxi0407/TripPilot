# Design

## Context
见 proposal.md。现有五角色图、Provider、ToolResult、Critic 和 ReAct 已实测；不复制业务逻辑。用户此次明确授权 V1.1 的协议进程、Harness 抽象与 checkpoint，V0.1 的不实现协议限制仅适用于旧版本。

## Goals / Non-Goals
以两天规模的本地 Demo 为边界：新增三个协议服务进程，仍是原有五个逻辑 Agent。没有队列、持久化、鉴权平台或分布式追踪设施；不会宣称生产级多租户安全或实时铁路。

## Decisions
- 使用 PyPI 排除预发布/撤回版本后的 mcp==2.2.0、a2a-sdk==1.1.5，按已发布 SDK 本身验证 API，不复制旧版本网上示例。MCP Streamable HTTP，A2A 官方 JSON-RPC binding 与标准 Card/Message/Task/Artifact。
- MCP 暴露 search_rail/search_poi/get_weather/calculate_distance/plan_route，输入和结构化输出复用 travel.py 的 Pydantic schemas，直接复用现有 Provider。旧 Registry 名称保留兼容映射。每次真实协议调用保留调用结果来源，禁止文本冒充。
- A2A 专家复用 research_transport/research_local，在独立进程中把 Registry 的实际执行连接到 MCP Client；主图 transport/local 节点通过 A2A 调度。Card 的 skills、返回 task/artifact、typed state delta 均验证。URL 在 Settings 集中配置并检查 Card endpoint 与配置来源一致。
- Harness 统一 RuntimePolicy、执行预算、重试与 schema 边界；保留 core.budget 等旧导入兼容入口，不重写 ReAct。可配置步骤8、重规划2、工具40、模型30、总时限180秒，以及外部调用、A2A/MCP/模型/工具超时、重试1次、重复阈值。
- 工具白名单与规范化输入指纹由 Harness 管理。缓存命中不再次访问 Provider；无新增 observation 的重复受阈值保护。向兼容 API 保留必要旧错误码，同时 runtime reason/trace 明确 TOOL_NOT_ALLOWED、DUPLICATE_TOOL_CALL、STEP_LIMIT_REACHED、TOOL_BUDGET_EXCEEDED。
- 外部调用按应用层外发操作计数，不声称等于 SDK 内部 TCP/HTTP 包数。专家携带有界预算租约和截止时间；主运行预留额度，收到合法 usage 后结算，超时未确认部分按已消耗处理，fallback 不能获得无限新预算。MCP 操作及其 Provider 外发成本纳入额度；失败与重试也计数。
- 重试在共享 Harness 层执行，底层 Provider 只翻译错误。认证、schema 输入错误、权限拒绝不重试。模型结构修复保留一次受控机会；它与瞬时网络重试共用上限。MCP/A2A 失败明确 FALLBACK 后才执行本地复用实现，不能改变 LIVE/Mock 数据来源。
- fixture 默认不依赖额外服务，保留117项离线测试；统一启动脚本启用协议路径。集成测试独立启动真实 SDK 服务，外部 Provider 用确定性数据；最终 LIVE 另显式执行。
- health 实际探测 MCP discovery 和两个 Agent Cards，缓存仅短期并注明状态；运行中按实际协议调用更新状态。UI 不以配置存在判断 CONNECTED/ONLINE，失败必须反映降级。
- 根目录 .env 不改写不复制；只有 MCP 服务和本地 fallback Provider 读取需要的凭据。协议消息不得携带 API Key，日志与 Trace 不含隐藏推理或原始异常。

## Risks / Trade-offs
- [远端超时后工作状态不确定] → 只读任务、子运行 deadline、标准取消及保守预算结算；不无条件重复整批操作。
- [MCP 不可达导致每工具重试放大] → 单运行连接失败标记与受控本地 fallback，后续运行重新探测。
- [Card/Artifact/schema 不可信] → 限定配置地址、验证技能与类型，拒绝超额 usage 和未知状态字段。
- [现场 API 波动/预报不覆盖 Dataset] → 显示失败或 partial，不伪造成功；保留 V0.2 基线回退。
- [SDK 新主版本] → 安装固定稳定包，按实际签名和集成测试验证；不使用 deprecated SDK client。

## Migration Plan
checkpoint 209918f 保持不变；新分支增量实现。先 strict 校验，再实现 Harness 与协议服务、主图、UI/脚本；完成离线和 LIVE 四场景。禁用 protocol 模式可回到同一代码中的本地专家执行；不自动 merge/push，不修改旧 change。
