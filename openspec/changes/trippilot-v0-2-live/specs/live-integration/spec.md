## Purpose
为 TripPilot 提供可验证的真实模型、地图工具与浏览器底图集成，明确区分配置状态、真实请求结果、合成铁路数据和天气模拟，在不泄露凭据的前提下展示完整旅行规划流程及其限制。

## ADDED Requirements

### Requirement: Credential-safe live execution
系统 SHALL 从根目录环境配置读取凭据，只展示配置状态和模型名称；真实调用失败 MUST 报告安全错误而非静默 Mock。
#### Scenario: Missing configuration
- **WHEN** 模型名或必要地图配置缺失
- **THEN** 对应服务标记为未配置，不宣称 LIVE，并允许独立服务继续验证。
#### Scenario: Canonical model configuration
- **WHEN** 配置 QWEN_CHAT_MODEL 或旧名称 QWEN_MODEL
- **THEN** 系统 SHALL 优先选择非空 QWEN_CHAT_MODEL，仅在其缺失时回退 QWEN_MODEL，并向所有模型调用入口提供同一模型配置值。
#### Scenario: Live structured model response
- **WHEN** Qwen 返回响应
- **THEN** 结构化结果经校验进入现有五 Agent 工作流，实际模型名可见，隐藏推理不进入 Trace。

### Requirement: Real Amap evidence and runtime status
系统 SHALL 验证 POI、天气、距离与路线的真实合同，标记 source=amap_live；Provider 状态 MUST 根据实际请求结果显示，铁路保持 Dataset/Mock。
#### Scenario: Successful or failed provider request
- **WHEN** 高德请求成功或认证、限流、网络失败
- **THEN** UI 区分 LIVE、FAILED、PENDING 与实际 MOCK，错误不包含凭据。
#### Scenario: Forecast out of range
- **WHEN** 行程超出真实预报范围
- **THEN** 显示未验证天气，不用合成天气冒充真实结果。

### Requirement: Interactive daily map
系统 SHALL 显示真实高德底图、当前日期 POI Marker 和名称，并自动调整视野；失败时保留可解释 fallback。
#### Scenario: Day selection
- **WHEN** 地图加载成功且用户切换行程日期
- **THEN** Marker 更新为当天 POI，并调整可视范围。
#### Scenario: Authentication or SDK failure
- **WHEN** 安全码缺失、鉴权失败或 SDK 超时
- **THEN** UI 显示明确失败原因和 POI/坐标 fallback，不宣称地图 LIVE。

### Requirement: Mixed-source revisions and regression
系统 SHALL 支持真实 Qwen/高德配合 Dataset 铁路的五天 Demo、明确标记的模拟暴雨修订和 200 元预算冲突；保留原离线测试。
#### Scenario: Simulated rain on live plan
- **WHEN** 用户选择模拟暴雨修订
- **THEN** 天气模拟单独标记，Critic 触发有限重规划，室内 POI 和路线来自真实工具。
#### Scenario: Impossible budget
- **WHEN** 总预算为 200 元且无法满足
- **THEN** 尝试有限调整后报告约束冲突，保留用户预算。
#### Scenario: Offline regression
- **WHEN** 运行默认自动化测试
- **THEN** 测试不读取真实凭据或调用付费 API，原 Mock 场景可重复。
