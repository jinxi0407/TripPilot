# TripPilot V0.1 验收记录

验收日期：2026-09-21。对应 OpenSpec：`trippilot-v0-1`，33 个任务，Phase A–K。

本记录证明本地合成数据 Demo 的实现与测试结果，不证明实时交通数据、真实模型质量或真实账户 API 可用性。未执行 commit、push 或归档。

## 环境与最终结果

macOS arm64，Python 3.13.2，Node 22.23.2，npm 10.5.0，OpenSpec 1.13.1。后端使用独立 `backend/.venv`；另在全新 `.tooling/verify-venv` 从锁定依赖安装成功，`pip check` 无损坏依赖，全部 90 项测试通过。未使用默认 Python 3.8，未修改系统 Python。

| 验证 | 实际结果 |
|---|---|
| 后端 pytest | 90 passed，含 24 个评估场景参数化用例 |
| Ruff | All checks passed |
| TypeScript + Vite production build | 通过 |
| Playwright 浏览器 E2E | 3 passed；一键 Demo 流程中浏览器异常和 console error 数组为空 |
| 独立 fixture evaluation | 24/24 符合预期；与 pytest 中对应场景有重叠，不累计为独立覆盖数 |
| OpenSpec strict validation | `Change 'trippilot-v0-1' is valid` |
| 本地服务 | FastAPI `127.0.0.1:8000`；Vite `127.0.0.1:5173` |
| Git / 密钥排除 | 检查工作区状态和未跟踪文本；无尾部空白、无匹配的真实密钥标记；根目录不存在 `.env`，`.env.example` 值全部为空 |

运行测试时有第三方 Starlette 对 AnyIO 别名的弃用警告；浏览器测试运行器有终端颜色环境变量提示。均不影响通过，未通过隐藏警告处理。没有真实外部 API 请求，后端测试的 HTTP 防护拒绝非 MockTransport / ASGITransport 的调用。

## 阶段实现与证据

| 阶段 | 实现和主要验证位置 |
|---|---|
| A | 独立 Python 环境、目录骨架、Settings、日志、健康检查；`test_health.py` |
| B | 统一 ModelClient、Qwen HTTP、结构化输出校验和一次修复、Mock；`test_model.py` |
| C | Provider 合同、五类只读工具、权限/输入输出校验/超时重试/缓存；`test_tools.py` |
| D | 五个逻辑 Agent、类型化 LangGraph 状态、日期澄清、路由；`test_supervisor.py` |
| E | Planner action/observation/final 循环、8 步/90 秒、全局预算、停止和 fallback；`test_planner.py`、`test_constraints_limits.py` |
| F | 确定性 Critic、六类费用核对、天气/交通/预算/路线修订、最多两次重规划；`test_critic.py`、`test_evaluation.py` |
| G | 创建/轮询/澄清/修订/取消 API、容量和过期、64 KiB 请求体；`test_api.py` |
| H | React 三栏、表单、行程卡、费用、版本与错误状态；前端 build 和 E2E |
| I | 安全 Agent Trace、工具耗时、地图区域与坐标 fallback；E2E 和截图 |
| J | 24 个场景、原始指标、单次 LLM baseline 入口、浏览器验收；`evals/`、`frontend/tests/demo.spec.ts` |
| K | 中文 README、真实截图、录屏脚本、限制与 MCP/A2A 后续边界；本文及文档审阅 |

## AC01–AC14 核对

| 验收项 | 结论与可复查证据 |
|---|---|
| AC01 需求与澄清 | 通过；三城五天、4000 元及偏好保留；缺日期经 UI 补充后完成 |
| AC02 五 Agent 与路由 | 通过；图集成和 Trace；同城用例跳过铁路 |
| AC03 铁路抽象 | 通过；Mock/Dataset 共享合同，Real 返回受控 unavailable；没有爬虫 |
| AC04 本地旅行工具 | 通过；POI/餐馆/路线/距离/天气的有效、空、异常、超时和不支持响应测试 |
| AC05 权限与脱敏 | 通过；未授权动作不触达 Provider，错误/Trace 的测试标记不泄漏；后端 Key 不进入前端 |
| AC06 有界执行 | 通过；8 步、90/180 秒、40 工具/30 模型、重试/修复计数、缓存/重复失败/取消；Local 使用确定性工具调用 |
| AC07 行程校验 | 通过；时间/开放/车站/换乘/密度/路线/遗漏城市；未知信息保留未验证项目 |
| AC08 预算 | 通过；整数分、六类费用、跨日铁路只计一次、未知票价不按零处理；200 元请求显示冲突 |
| AC09 重规划 | 通过；天气、交通、预算、路线修订用例；全局最多两次，重复问题提前停止 |
| AC10 任务 API | 通过；202/404/409/422/503、取消、过期、容量、终态保护；另验证 413 |
| AC11 桌面/移动界面 | 通过；1440px 和 390px，移动端无水平溢出，行程/费用/来源/Trace/地图 fallback 可见 |
| AC12 无 Key Demo | 通过；新环境测试及运行中的完整浏览器 Demo；Qwen 适配器仅模拟 HTTP 测试，真实联调未执行 |
| AC13 评估 | 通过；24 条版本化 JSONL、10 类指标及分母/缺失值、原始报告；真实模型比较明确 `not_run` |
| AC14 文档准确性 | 通过；启动/测试命令实际执行；限制、录屏方法和未来协议边界明确，无未测量提升百分比 |

## 浏览器与 Demo 证据

测试 1：一键 Demo 得到 5 天行程；暴雨修订得到版本 2，首日西湖替换为浙江省博物馆；预算改为 200 元后出现明确预算冲突。整个流程没有页面异常或 console error。

测试 2：390px 窄屏普通提交先要求日期，补充 `2026-10-10` 后完成；切换 Day 3 可查看明城墙，没有水平溢出。

测试 3：通过 fixture scenario 注入 Provider outage，UI 显示“这次规划暂未完成”和受控服务错误，任务为 `failed`，不把服务失败描述成用户约束冲突。

截图均由真实本地浏览器测试生成，已人工视觉检查：

- [桌面行程](screenshots/demo-desktop.png)
- [移动布局](screenshots/demo-mobile.png)
- [服务故障](screenshots/provider-outage.png)

内置浏览器工具未提供可用实例，因此使用项目内 Playwright 和已安装 Chrome 的独立临时配置完成验收。没有使用用户浏览器账户。

## 复现命令

从仓库根目录执行；服务启动命令见 [README](../README.md)。

```sh
backend/.venv/bin/python -m pytest -q -c backend/pyproject.toml backend/tests
backend/.venv/bin/ruff check backend/app backend/tests evals
export PATH="$PWD/.tooling/runtime/node_modules/.bin:$PWD/.tooling/openspec/bin:$PATH"
npm --prefix frontend run build
frontend/node_modules/.bin/playwright test --config frontend/playwright.config.ts
PYTHONPATH=backend backend/.venv/bin/python -m evals.runner
OPENSPEC_TELEMETRY=0 openspec validate trippilot-v0-1 --strict --no-interactive
```

原始评估结果见 [fixture-results.json](../evals/reports/fixture-results.json)，包含执行时间、证据哈希、逐例状态、指标原始计数与耗时。合成策略没有模型 Token 消耗，记作 `null`。故障、澄清和冲突的正确处理也属于符合预期，不将 24/24 解读为实时旅行成功率。

## 当前边界与手动事项

- 无需手动提供任何 Key 即可展示 Mock。真实 Qwen 需要本地配置 `DASHSCOPE_API_KEY` / `QWEN_CHAT_MODEL`（兼容旧 `QWEN_MODEL`） 及匹配账户区域的端点；真实高德需要 Web Service Key 和对应权限。未发起付费调用。
- Mock 主要覆盖上海、杭州、南京、苏州，Demo 使用固定日期的合成信息；真实 Qwen/Amap 适配器未完成真实账户联调。
- Rail Mock 和 Dataset 已实现；RealRailProvider 是受控占位，尚无授权实时车次/余票服务。
- 地图为路线示意、POI 与 GCJ-02 坐标 fallback；互动高德地图 SDK 未接入。
- 进程内任务存储会在重启时清空；不是生产部署，没有认证、支付、订票或酒店预订。
- 无酒店地址时不验证酒店接驳；未知开放时间、票价或天气保持不确定状态。模型输出可能只达到 `partial`，不能承诺所有真实请求都有可行解。
- Baseline 比较入口和模拟验证已实现，真实 Qwen 比较未运行，无性能提升结论。
- Git 仓库尚无提交，项目文件为未跟踪状态，所以额外审阅了未跟踪文件；仅看 `git diff` 无法覆盖这些内容。`.env`、虚拟环境、Node 依赖、构建输出、本地工具与测试临时目录均已忽略。未 commit / push / 自动归档。
