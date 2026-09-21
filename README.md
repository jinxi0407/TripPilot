# TripPilot

**Multi-Agent AI Travel Planner · 让每一步，都刚刚好。**

TripPilot 是面向中国大陆旅行场景的本地 AI 应用 Demo。它通过 **LangGraph、Multi-Agent、ReAct 和 Tool Calling**，把旅行需求拆成铁路研究、本地景点/天气/路线研究、行程编排，以及预算和可行性校验。

它能生成带来源标签的多日行程，在暴雨、交通变化或预算冲突时进行有上限的 **Dynamic Replanning**。目前支持无需任何 Key 的完整 Mock Demo；真实 Qwen 和 Amap HTTP 适配器已经实现。V0.2 已实测 Qwen `qwen-plus`、高德 POI/天气/距离/路线及真实浏览器底图和 Marker。完整五天图流程使用真实模型和高德，铁路仍为 Dataset；未知信息如实保留。

![TripPilot 桌面 Demo](docs/screenshots/demo-desktop.png)

**V0.2 联调状态：** Qwen、高德 Web Service 与 JS 地图已通过真实调用验证，Provider 标签来自实际运行结果。详见 [V0.2 验收记录](docs/v0.2-live-report.md)。

[手机布局截图](docs/screenshots/demo-mobile.png) · [故障降级截图](docs/screenshots/provider-outage.png) · [录屏演示脚本](docs/demo-guide.md)

## 快速体验

打开前端后，点击左侧 **「三城慢游 · 历史与夜色」**。这会运行真实的本地工作流，而不是仅展示一张预设结果卡片：

> 我想从上海出发，用5天游玩杭州、南京和苏州。预算4000元，喜欢历史景点和夜景，不想每天太赶。请结合高铁、天气、景点位置和市内交通帮我规划行程。

Demo 明确使用 **2026-10-10 起的合成证据**。列车标记为 `DEMO-G…`，天气、票价、开放时间及路线耗时均不代表实时信息。普通请求缺少日期时会先要求补充。Mock 的中文解析主要覆盖上海、杭州、南京、苏州；其他城市需要真实模型与相应 Provider 数据支持，不能保证完整覆盖。

## 架构与 Multi-Agent 工作流

```mermaid
flowchart LR
    UI[React / Vite / TypeScript] --> API[FastAPI 本地 API]
    API --> S[Supervisor]
    S --> T[Transport]
    S --> L[Local Travel]
    T --> P[Travel Planner]
    L --> P
    P --> C[Critic]
    C -->|反馈，最多两次重规划| S
    C --> R[完成 / 待确认 / 冲突]
    T --> Tools[受控 Tool Registry]
    L --> Tools
    P --> Tools
    Tools --> Rail[RailProvider]
    Tools --> Amap[AmapProvider / Mock]
```

| 角色 | 职责 |
|---|---|
| Supervisor | 结构化约束提取、日期澄清、确定性路由；同城行程跳过铁路 |
| Transport | Rail Search，获取有来源的车站、时刻、费用、换乘信息 |
| Local Travel | 景点、室内备选、天气及市内交通研究；使用正常工具调用 |
| Travel Planner | ReAct 选择工具、读取 Observation、组合与修订行程 |
| Critic | 时间、车站缓冲、换乘、开放时间、密度、天气、路线及预算校验 |

五个逻辑 Agent 在一个 FastAPI/LangGraph 进程中运行。Provider、Tool、Schema、API 和业务服务分目录存放；没有微服务或外部消息队列。任务存储在内存中，进程重启后不保留。

## ReAct 与执行边界

Planner 的每一步产生结构化 `action` 或 `final` 决策。Action 只能访问注册且授权的工具，Observation 带结构化数据和错误码，随后再决定下一步。Mock 模式用可重复的策略代替模型决策；Qwen 模式通过同一接口请求结构化决策。Mock 演示不等于真实 LLM 推理质量证明。

- 每轮 Planner 最多 **8 步**，单轮 **90 秒**；一次运行最多 **180 秒活动执行时间**。
- 全局最多 **40 次工具尝试**、**30 次模型尝试**，重试和格式修复也计数。
- 工具超时 **10 秒**，模型超时 **30 秒**；可重试错误最多重试一次。
- 成功的重复调用复用缓存，重复失败调用停止；注册表拒绝越权及写操作。
- Critic 最多触发 **2 次重规划**；相同问题修复无效时提前停止。
- UI Trace 只展示安全的工具动作、结果摘要、时序和耗时，不展示私有 chain-of-thought、提示词或密钥。

## Amap 与 RailProvider

高德作为工具提供方，封装 `AmapPOITool`、`AmapRouteTool`、`AmapDistanceTool`、`AmapWeatherTool`。真实适配器支持 POI/餐馆、步行/驾车/公交路线、距离和天气，具体可用性受账户权限和覆盖范围限制。公交、预报日期等不支持时返回受控结果；缺少开放时间或票价会保留未知状态。坐标统一标注 **GCJ-02**。

未提供 `AMAP_API_KEY` 时使用 `MockAmapProvider` 并标注来源。即使 Qwen 为真实模型，也可能组合 Mock 铁路/高德数据，不能把整份结果当作实时计划。

| Rail Provider | 当前状态 |
|---|---|
| `MockRailProvider` | 已实现，可重复的合成直达车次 |
| `DatasetRailProvider` | 已实现，版本化日期固定的直达/换乘数据集 |
| `RealRailProvider` | 接口占位，返回未配置；等待合法授权 API |

没有 12306 爬虫、出票或购票操作。高德浏览器地图与 Web Service Key 是不同接入面；当前已接入高德 JS API 2.0、当天 Marker 和自动视野，同时保留 POI/坐标 fallback。安全码由后端 `/_AMapService` 代理添加，Web Service Key 不进入浏览器。真实底图、Marker 名称、日切换与自动视野已在独立 Chrome 中验收。

官方接口参考：[Qwen 调用说明](https://help.aliyun.com/en/model-studio/first-api-call-to-qwen)、[高德路线 API](https://lbs.amap.com/api/webservice/guide/api/direction)、[高德 POI API](https://lbs.amap.com/api/webservice/guide/api/search/)。账户区域、模型和服务权限需要在真实联调前核对。

## Constraint-aware Planning 与 Critic

Critic 输出 `valid`、`issues`、每条问题的 `severity` / `suggestion`、已检查约束和未验证项目。已知硬冲突不能被包装为成功；未知信息产生 `partial`，无法满足的硬约束产生 `conflict`。

费用按整数分计算：城际交通、市内交通、住宿占位、景点门票、餐饮估算、备用金。每日费用、分类费用与总额核对；未知票价不按零处理，跨日铁路只计费一次。默认一位成人、不自动添加返程；酒店和住址未提供时不推测接驳位置。

「模拟暴雨 · 重规划」会更新模拟天气，产生新版本，将受影响的户外活动改到室内，重新查询缺失路线并整体验证。更新交通、调整预算和重新检查路线也创建关联的新任务，旧版行程在新版生成期间保留。

## 本地环境与安装

已在 macOS arm64、Python **3.13.2**、Node **22.23.2** 上验证。不要使用本机默认 Python 3.8。

在仓库根目录运行：

```sh
/usr/local/bin/python3.13 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
export PATH="$PWD/.tooling/runtime/node_modules/.bin:$PATH"
npm --prefix frontend ci
```

`.tooling/` 是本机安装、已忽略的 Node/OpenSpec 目录，新克隆不包含它。其他机器先安装兼容 Node 22，再直接使用 `npm`；Python 可用其他兼容的 >=3.11 解释器替换上述绝对路径。依赖锁定在 `backend/requirements.txt` 和 `frontend/package-lock.json`。

## 环境变量与 Mock Mode

**不配置任何 Key 即可启动、测试和完成 Demo。** 本地 `.env` 由用户填写并被 Git 忽略；`.env.example` 始终只有空占位符。不要展示或提交本地凭据。

| 变量 | 用途 |
|---|---|
| `DASHSCOPE_API_KEY` | 真实 Qwen 认证，仅后端读取 |
| `QWEN_CHAT_MODEL` | 首选模型变量，账户可用的模型 ID，无硬编码默认模型 |
| `QWEN_MODEL` | 旧版兼容回退；首选变量非空时不生效，无需同时填写 |
| `DASHSCOPE_BASE_URL` | DashScope 兼容 API 地址；留空采用原有默认值 |
| `AMAP_API_KEY` | 高德 Web Service Key，仅后端读取 |
| `VITE_AMAP_JS_KEY` | 浏览器地图 SDK 的 JS API Key，与 Web Service Key 分开 |
| `VITE_AMAP_SECURITY_CODE` | 配套安全码；由后端读取并代理附加，不编入浏览器代码 |
| `RAIL_PROVIDER` | 空或 `mock` / `dataset` / `real` |
| `RAIL_API_KEY` | 未来授权铁路适配器预留，当前不使用 |

如要配置真实调用，在本机环境变量或本地 `.env` 中自行填写，不要提交或把 Key 发到聊天中。Settings 会读取仓库根目录的 `.env`。模型只保留一个内部值，优先读取非空 `QWEN_CHAT_MODEL`，不存在时回退到 `QWEN_MODEL`；同名变量由进程环境优先于 `.env`，旧名称不会覆盖 `.env` 中的首选名称。默认 DashScope 地址为北京兼容接口；若账户要求 Workspace 专属域名或其他区域，可额外设置 `DASHSCOPE_BASE_URL` 为控制台提供的完整兼容 API Base URL（HTTPS，阿里云域名）。模型/账户不匹配会返回受控错误，不会静默伪造实时结果。

- `fixture`：固定模拟模型和高德数据；铁路按配置选择，默认 Mock。
- `auto`：有完整 Qwen 配置时使用 Qwen，否则使用 Mock；高德也独立按 Key 选择。
- `live`：明确要求 Qwen，配置不足时返回提示；高德无 Key 仍采用带标签的 Mock。
- 直接注入雨天/故障场景只允许 `fixture`；真实行程的“模拟暴雨”修订会明确标注模拟来源，POI/路线继续查询真实高德。
- Demo 卡片遵循当前模式选择，不再强制切换 Mock。默认 `auto`；真实联调请选择 `live`，缺模型配置会失败。
- 页面 Provider 标签来自本次请求：`PENDING` 尚未验证、`LIVE` 调用成功、`FAILED` 真实调用失败、`MOCK` 实际模拟、`DATASET` 实际数据集。失败不会静默切换成 Mock。

## 启动 Backend

终端 1，在仓库根目录：

```sh
cd backend
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

健康检查：<http://127.0.0.1:8000/health>；API 文档：<http://127.0.0.1:8000/docs>。

## 启动 Frontend

终端 2，在仓库根目录：

```sh
export PATH="$PWD/.tooling/runtime/node_modules/.bin:$PATH"
cd frontend
npm run dev
```

打开 <http://127.0.0.1:5173>。Vite 代理 `/api` 和 `/health` 到本地后端。UI 使用短轮询，未引入 SSE/WebSocket。

主要 API：

| 方法 | 路径 | 行为 |
|---|---|---|
| GET | `/health` | 结构化健康状态，不返回凭据 |
| POST | `/api/plan` 或 `/api/v1/plans` | 202 返回 `run_id` / `task_id` 和轮询地址 |
| GET | `/api/trace/{task_id}` 或 `/api/v1/plans/{task_id}` | 状态、Trace、结果；支持 `after_sequence` |
| POST | `/api/v1/plans/{task_id}/clarifications` | 按 `expected_revision` 补充信息 |
| POST | `/api/v1/plans/{task_id}/revisions` | 天气/交通/预算/路线修订 |
| POST | `/api/v1/plans/{task_id}/cancel` | 幂等取消 |

最多 2 个活动任务，最多保留 50 个已结束任务，保留时间 60 分钟；进程重启清空。请求体上限 64 KiB。状态包括 `needs_clarification`、`completed`、`partial`、`conflict`、`failed`、`cancelled`。

## Tests

```sh
# 仓库根目录：后端测试隔离本地 .env，禁止真实外部 HTTP
backend/.venv/bin/python -m pytest -q -c backend/pyproject.toml backend/tests
backend/.venv/bin/ruff check backend/app backend/tests backend/live_check.py evals
npm --prefix frontend test
npm --prefix frontend run build

# 先启动前后端；浏览器 E2E 使用独立临时浏览器配置
export PATH="$PWD/.tooling/runtime/node_modules/.bin:$PATH"
frontend/node_modules/.bin/playwright test --config frontend/playwright.config.ts
```

macOS 测试默认使用已安装的 Google Chrome；其他环境可先执行 `cd frontend && npx playwright install chromium`。测试涵盖工具合同、权限、超时、Qwen 错误/修复、路由、ReAct 限制、Critic、预算、重规划、API 生命周期以及浏览器流程。

## Evaluation

```sh
PYTHONPATH=backend backend/.venv/bin/python -m evals.runner
```

24 个固定场景见 [cases.jsonl](evals/cases.jsonl)，原始计数、耗时、证据哈希见 [fixture-results.json](evals/reports/fixture-results.json)。最后一次本地运行 **24/24 符合预期**；其中包括正确澄清、拒绝冲突和故障降级，并不是 24 份真实旅行计划都成功。

指标包括任务预期完成、路由正确性、工具选择、约束满足、预算合规、路线可行性、无依据交通声明、Agent 步数、延迟及 Token 用量。Fixture 没有真实 Token 消耗记录，Token 为 `null`。延迟只代表本地合成工作流，不能用来声称真实模型响应速度。

[简单单次 LLM 与 Multi-Agent 比较入口](evals/compare.py) 已实现，双方使用同一模型设置、合成证据空间和确定性校验器。**真实比较未运行，无提升百分比。** 如以后允许付费真实模型评估，可配置账户后手动运行：

```sh
PYTHONPATH=backend backend/.venv/bin/python -m evals.compare --allow-paid-model --case 01
```

错误草案注入属于 fixture 控制实验，真实模型比较会单独记录其测试范围。详见 [评估定义](docs/evaluation-plan.md)。

## 已知边界与 Future MCP/A2A

- 这是本地求职展示项目，不提供支付、购票、酒店预订或生产级认证。
- 高德四类接口和 Qwen qwen-plus 均有真实请求证据。实时开放时间、票价、预报可能缺失，结果可为 partial。
- Mock 的行程编排采用可重复策略，不是通用中文理解器或全局最优路线求解器。
- 数据集日期覆盖有限；超出范围的天气和铁路不会被当作已知。没有酒店地址时不验证酒店接驳。
- 真实互动地图已验收；授权实时铁路与 FlightProvider 未实现。
- 未来 MCP 可把 rail/POI/route/distance/weather 工具暴露为外部服务，保留 Registry 权限和执行预算。
- 未来 A2A 可将 Transport 或 Local Travel 独立部署，通过类型化任务交互；当前没有为了展示协议增加分布式设施。

## 工程与 OpenSpec

[AGENTS.md](AGENTS.md) · [设计](openspec/changes/trippilot-v0-1/design.md) · [33 项任务](openspec/changes/trippilot-v0-1/tasks.md) · [验收记录](docs/acceptance-report.md)

```sh
export PATH="$PWD/.tooling/runtime/node_modules/.bin:$PWD/.tooling/openspec/bin:$PATH"
OPENSPEC_TELEMETRY=0 openspec validate trippilot-v0-1 --strict --no-interactive
```

本次不会 commit、push 或自动归档 OpenSpec。后续可在审阅后再决定这些操作。
