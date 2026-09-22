## Purpose
为现有旅行工作流增加可控会话延续、结构化长期偏好、基于实际行程的住宿推荐和有来源的铁路航空比较，同时保留真实协议执行与原运行保护，不新增旅行智能体或订票能力。

## ADDED Requirements

### Requirement: Session and opt-in preference memory
系统 SHALL 延续当前会话行程、日期、预算、约束、修订、交通/住宿选择和重规划历史；长期存储只包含结构化偏好，支持保存、加载、更新、清除，remember=false 不写入。
#### Scenario: Continue day two
- **WHEN** 当前杭州三日行程收到“第二天不要安排户外活动”
- **THEN** 系统保留城市日期预算并将 Day2 室内约束用于新版本，其他会话不受影响。
#### Scenario: Persistence and priority
- **WHEN** 保存 relaxed/历史/夜景/避早班/近地铁后发起新南京请求，本次明确 compact
- **THEN** 加载其他可复用偏好且本次 compact 胜过会话和长期 relaxed；Trace 只显示加载摘要。
#### Scenario: Malformed or cleared memory
- **WHEN** 清除偏好或存储内容不符合 schema
- **THEN** 不加载非法内容，安全返回空偏好或明确受控错误，不永久记录原聊天。

### Requirement: Itinerary aware hotel recommendation
系统 SHALL 从复用的高德Provider查询真实Hotel POI，返回名称、地址、坐标、区域、来源及可用距离/路线；按日景点区域、车站便利性和偏好推荐区域/理由/候选，缺失信息保留未知。
#### Scenario: Three city accommodation
- **WHEN** 五天三城行程启用住宿推荐
- **THEN** 每个住宿城市有区域和依据、Hotel POI candidates，LIVE查询来源标记为amap_live，实时价格/库存/可订状态明确未接入。
#### Scenario: Excessive detour
- **WHEN** 酒店到景点或车站明显过远/绕路
- **THEN** Critic报告HOTEL_TOO_FAR、HOTEL_ROUTE_INEFFICIENT或HOTEL_STATION_ACCESS_POOR，最多一次住宿重选且计入全局重规划上限。

### Requirement: Flight and door to door comparison
系统 SHALL 提供带航班号、机场、时刻、时长、价格可空、来源、可用性和模式的航空候选，优先使用合法授权Provider，无凭据使用固定Dataset。比较 SHALL 纳入两端接驳、推荐缓冲、旅行时长、换乘和偏好/早班因素，估计与未知显式区分。
#### Scenario: Beijing to Shanghai
- **WHEN** 请求北京到上海铁路航空比较
- **THEN** 展示Rail DATASET与Flight DATASET、可核对的门到门分项和推荐理由，不声称最优或实时库存，偏好不掩盖合理备选。
#### Scenario: Missing or unavailable flight
- **WHEN** 航班价格缺失或标记不可用
- **THEN** 价格保持unknown，不选择不可用航班或伪造精确费用。

### Requirement: Seven tools with original specialists and harness
系统 SHALL 真实发现并调用search_rail/search_flights/search_poi/search_hotels/get_weather/calculate_distance/plan_route七个MCP工具，仍只有两个A2A专家，新增能力受原Harness/ReAct/Critic控制。
#### Scenario: Full protocol product run
- **WHEN** 运行含交通比较和住宿的规划
- **THEN** Transport通过MCP查询铁路/航班，Local Travel通过MCP查询酒店/POI/天气/路线，标准Artifact合入State，runtime状态来自实际调用。
#### Scenario: Existing behavior and UI
- **WHEN** 旧五天、暴雨或200元请求及新偏好/住宿/交通请求运行
- **THEN** 原回归仍正常，UI增量展示偏好开关/清除、住宿和比较卡片、安全Trace与Memory/Hotel/Flight实际状态，所有Key保持私密。
