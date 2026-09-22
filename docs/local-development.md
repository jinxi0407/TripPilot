# 本地开发与验证

所有命令从仓库根目录执行。新克隆需要自行安装 Python >=3.11 和 Node 22；`.tooling/` 中的本机工具不会上传。

## 本地环境与安装

已在 macOS arm64、Python **3.13.2**、Node **22.23.2** 上验证。不要使用本机默认 Python 3.8。

在仓库根目录运行：

```sh
python3 -m venv backend/.venv
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
| `FLIGHT_PROVIDER` | 留空默认为 `dataset`；`real` 为未接入的授权接口边界 |
| `MEMORY_DATABASE` | 留空采用 `.tooling/preferences.sqlite3` 本地偏好库 |

如要配置真实调用，在本机环境变量或本地 `.env` 中自行填写，不要提交或把 Key 发到聊天中。Settings 会读取仓库根目录的 `.env`。模型只保留一个内部值，优先读取非空 `QWEN_CHAT_MODEL`，不存在时回退到 `QWEN_MODEL`；同名变量由进程环境优先于 `.env`，旧名称不会覆盖 `.env` 中的首选名称。默认 DashScope 地址为北京兼容接口；若账户要求 Workspace 专属域名或其他区域，可额外设置 `DASHSCOPE_BASE_URL` 为控制台提供的完整兼容 API Base URL（HTTPS，阿里云域名）。模型/账户不匹配会返回受控错误，不会静默伪造实时结果。

- `fixture`：固定模拟模型和高德数据；铁路按配置选择，默认 Mock。
- `auto`：有完整 Qwen 配置时使用 Qwen，否则使用 Mock；高德也独立按 Key 选择。
- `live`：明确要求 Qwen，配置不足时返回提示；高德无 Key 仍采用带标签的 Mock。
- 直接注入雨天/故障场景只允许 `fixture`；真实行程的“模拟暴雨”修订会明确标注模拟来源，POI/路线继续查询真实高德。
- Demo 卡片遵循当前模式选择，不再强制切换 Mock。默认 `auto`；真实联调请选择 `live`，缺模型配置会失败。
- 页面 Provider 标签来自本次请求：`PENDING` 尚未验证、`LIVE` 调用成功、`FAILED` 真实调用失败、`MOCK` 实际模拟、`DATASET` 实际数据集。失败不会静默切换成 Mock。

## 启动 V1.2 Backend 服务

终端 1，在仓库根目录，一条命令启动四个独立进程：

```sh
./scripts/dev_v1_2.sh
```

默认端口：主后端 `8000`、Transport A2A `8101`、Local Travel A2A `8102`、Travel MCP `8200`。启动器通过进程环境启用协议，读取根目录 `.env`，不复制凭据；端口占用时直接停止启动，不终止已有程序。Ctrl+C 清理本次启动的子进程；单个协议服务故障时其余服务继续运行并允许受控 fallback。日志和 PID 清单写入已忽略的 `.tooling/v11/`。

配置集中在 `Settings`：`MAIN_PORT`、`MCP_URL`、`A2A_TRANSPORT_URL`、`A2A_LOCAL_URL`；协议地址只允许本机 HTTP。`PROTOCOLS_ENABLED` 控制主进程是否使用协议，启动器自动启用。各服务均可从 `backend/` 独立启动：

```sh
.venv/bin/python -m uvicorn app.mcp.server:create_app --factory --host 127.0.0.1 --port 8200 --no-access-log
.venv/bin/python -m uvicorn app.a2a.service:transport_app --factory --host 127.0.0.1 --port 8101 --no-access-log
.venv/bin/python -m uvicorn app.a2a.service:local_app --factory --host 127.0.0.1 --port 8102 --no-access-log
PROTOCOLS_ENABLED=true .venv/bin/python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

四条独立启动命令分别占用终端；端口调整时同时更新对应配置。原 V0.2 单进程入口 `app.main:app` 仍可用，未启用协议时显示 DISABLED。

策略由 `backend/app/harness/policy.py` 统一定义，可用嵌套环境变量覆盖，例如 `RUNTIME_POLICY__MAX_TOOL_CALLS=40`、`RUNTIME_POLICY__MCP_TIMEOUT_SECONDS=15`。所有服务使用同一配置。修改 `.env` 后重启服务，Vite 的主后端代理端口跟随 `MAIN_PORT`。

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
PYTHONPATH=.:backend backend/.venv/bin/python -m pytest -q backend/tests
backend/.venv/bin/ruff check backend/app backend/tests backend/live_check.py evals scripts
npm --prefix frontend test
npm --prefix frontend run build

# 先启动前后端；浏览器 E2E 使用独立临时浏览器配置
export PATH="$PWD/.tooling/runtime/node_modules/.bin:$PATH"
frontend/node_modules/.bin/playwright test --config frontend/playwright.config.ts
```

发布回归：**215 后端测试**、**1 前端单元测试**、**24 浏览器测试**全部通过。协议测试真实监听临时本地 TCP 端口，调用官方 SDK；只允许 loopback HTTP，不消耗真实 Provider API。LIVE 浏览器证据另存于验收报告，不能与 Mock 回归混淆。

macOS 测试默认使用已安装的 Google Chrome；其他环境可先执行 `cd frontend && npx playwright install chromium`。测试涵盖工具合同、权限、超时、Qwen 错误/修复、路由、ReAct 限制、Critic、预算、重规划、API 生命周期以及浏览器流程。


## OpenSpec

安装与项目一致的 CLI 后执行：

```sh
npm install --prefix .tooling/openspec @fission-ai/openspec@1.13.1
OPENSPEC_TELEMETRY=0 .tooling/openspec/node_modules/.bin/openspec validate --all --strict --no-interactive
```

最新 V1.2.2 变更已完成同步和归档，旧版本开发记录保留在 `openspec/changes/`。
