# Design

## Context
见 proposal。现有 RunService/RunStore 管理任务版本与修订，AgentState 是 LangGraph TypedDict，Itinerary 只接受 RailOption。Local Travel 使用 Registry，A2A Artifact 为受控 SpecialistDelta；MCP 目前五个合同，两个专家仍复用现有研究函数。现有141测试是兼容基线。

## Goals / Non-Goals
在原五角色中加入产品能力和可复现测量，不重写图或 Harness。以两天规模的本地作品为边界：默认 local user、标准库 SQLite、小型固定数据、串行 Benchmark；不做持久化聊天、实时航空/酒店库存、预订、鉴权、向量检索或新服务。

## Decisions
- Memory 采用类型化 Preferences + 有界内存 SessionStore。API 显式 session_id；保存当前 constraints/itinerary、修订摘要、选择和历史，不以隐式全局聊天串污染不同会话。SQLite 仅保存偏好 JSON 及版本，不保存原文；remember=false 不写入，clear 删除偏好。请求解析出的非默认/显式字段覆盖会话，再覆盖长期偏好；否定/当前覆盖不能被默认值反向覆盖。
- 酒店复用 AmapProvider._get 的 POI 接口，返回 HotelCandidate 类型及证据，不增第二个 HTTP client。Local Travel 按已有城市行程分布和候选日 POI 查询酒店，对候选与活动中心做距离评分，择优查询到主要 POI/车站路线；Planner 对最终选中日 POI 重新评分。无法验证地铁时保留未知，不把名称猜测当接驳事实。Critic 的酒店过远/绕路/站点检查可触发最多一次重选，计入原重规划次数。
- FlightOption 与 RailOption 分开，Itinerary day 可包含其中一种；TravelTimeEstimate 显式接驳、缓冲、线路耗时与来源，未知就 null，估计标 estimate。Dataset 文件固定日期/合成编号/库存 unknown；RealFlightProvider 返回未配置。Transport 通过 search_flights 获取候选并与铁路同时展示，偏好只作排序因素，硬限制单独表达。
- MCP 七合同及 A2A Delta 扩展类型化航班、酒店和比较数据，严格允许字段/用量校验。新增工具归原专家；只有需要的功能才调用。有限候选（每城最多3酒店、择优路线）控制调用数，必要预算从统一 policy 配置调整，不给失败流程重置预算。
- Benchmark 输入独立于 evaluator 标签，生产组件不得导入 evals。50题先固定并检查字段、类别分布、目的地/时间/预算一致性和唯一性。固定 Rail/Flight/Amap fixture 为双方同等证据，Qwen 均 qwen-plus/temperature0；fixture Provider 与模型选择解耦，协议专家也收到 source_mode。单 Agent 使用同一工具合同和装配器，但不调用专家/独立 Critic/重规划图，不能额外提供 ground truth。
- 评估按结构化证据计算目的地、费用、日期/时间、天气/换乘、记忆覆盖、酒店来源与地理关联、交通门到门及 unsupported claims。正确不可满足算 task success，但 constraint raw satisfaction 仍独立记录，未知不算已满足；安全停止不等于恢复成功。工具集合指标来自实际 Registry 记录，路由来自结构化图数据与 Trace。无分母为 N/A，不填100%。
- Benchmark 每例 JSONL append+flush，run manifest 固定输入/数据/配置/代码哈希，resume 校验签名避免混合版本。串行100次架构运行，模型每例最多12次、总最多1200次，每轮步骤8、每例240秒（两架构模型超时统一60秒，预检发现批量结构化输出可能超过原30秒），整体8小时安全界限；guard 达限保存 partial，不伪造结果。Token 仅 API usage，失败未返回则 unavailable。每5题输出安全进度，原始模型隐藏推理不落盘。通用 bug 修复须记录且重新执行整个固定50题，不改标签迎合结果。
- 另10故障通过真实本地协议/可控Provider和模型故障注入验证检测/恢复/降级，单列结果不混入50。Benchmark之后5例真实Qwen/高德/酒店/协议 smoke，覆盖6类演示（可共享五天场景与酒店场景）。前端沿用现有卡片样式与来源标签。

## Risks / Trade-offs
- [100次真实模型调用耗时与费用] → 串行、上限、断点续跑；使用用户已授权凭据，不购买新服务，失败实报。
- [偏好隐式覆盖本次意图] → 保存结构化字段、记录有效偏好来源，显式覆盖测试与会话隔离。
- [推荐住宿无真实价格/库存] → 输出字段不提供假价格，UI明确需OTA确认；住宿预算仍只是预算占位。
- [实际行程改动造成住宿绕路] → 按最终选点再评分、Critic一次重选与全局上限。
- [较远城市无数据] → 标记缺口或约束冲突，不补假实时来源；样本覆盖与失败完整报告。
- [评估对旧启发式偏好] → 基线与系统共用数据/工具/装配器/evaluator，披露共享确定性组件及单次运行限制，不宣称因果性能提升。

## Migration Plan
先检查点与规格strict，后增量实现与测试。SQLite 文件被Git忽略，旧请求字段兼容可选新字段。旧changes不修改；V1.1 b66dc59和V0.2 209918f均保留。实测后只记录真实数字，不自动commit V1.2、push、merge或继续新增功能。
