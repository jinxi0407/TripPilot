# 最终精简审计

日期：2026-09-22。审计起点：`a6e1d1c`。本文件在删除操作之前建立，记录保留与删除判断，完成后补充实际验证结果。范围包括全部 302 个受 Git 管理文件，以及 ignored 本地工具、缓存、日志和开发中间产物。根目录 `.env` 仅用于配置状态/内存密钥匹配，不输出内容。

## 审计方式

对照 README、最终简历、LangGraph 调度、动态 CLI factory、工具注册表、测试、启动脚本和文档引用。以文件引用和实际调用路径联合判断；单纯“没有 import”不作为删除依据。固定 Benchmark 和核心后端代码先保存哈希，以回归验证低风险清理。

## A. 必须保留

| 范围 | 判断依据 |
| --- | --- |
| `backend/app/agents/`、`graph/`、`services/` | 五 Agent 工作流、ReAct、Critic confirmed/blocking gate、行程装配和有界修订；受现有测试和 Benchmark manifest 覆盖。 |
| `backend/app/a2a/`、`mcp/`、`tools/` | 两个独立 A2A 服务、Agent Cards、7 个 MCP 合同、权限及结构化结果；HTTP 集成测试实际调用。 |
| `backend/app/harness/`、`core/`、`schemas/` | 运行预算、超时、重试、配置、安全日志和 schema 不变量；非装饰性抽象。 |
| `backend/app/persistence/` | 任务状态、Session 与 SQLite 偏好；重启语义和隐私边界有测试。 |
| `backend/app/providers/` 及 `data/` | Amap / Hotel、Rail / Flight、Mock / Dataset 均被 factory、测试或评测调用。两个铁路文件由同一 Provider 合并加载，不能误删旧 `rail.json`。 |
| FastAPI `main.py`、`api/` | 主入口、地图安全代理、健康检查、兼容 API；别名路由由 `test_api.py` 验证。 |
| `frontend/src/` 所有现存组件 | App/组件树均有引用，包含旅行/演示模式、地图、天气、Trace、酒店、交通比较、偏好及校验 UI。只删除已不存在 DOM 对应的样式和隐藏旧导航。 |
| `backend/tests/`、`frontend/tests/`、`frontend/unit/` | 全部正式测试保留，不按目标数量删改断言。 |
| `evals/v1_2/`、`v1_2_2/`、`baseline/` | 固定 50 题、两个版本正式结果、历史 88%、最终 96%/64%、故障注入与 Single-Agent 证据；整目录内容不改写。 |
| `openspec/`、`.agents/skills/` | 有效设计与开发历史。最新 V1.2.2 已归档，其余已完成 change 的历史不当作失败草稿删除。 |
| 最终截图、架构 SVG、验收报告、简历核验 | 求职展示和真实联调证据，保留相对链接。 |
| `scripts/dev_v1_2.sh` → `dev_v1_1.sh` → `dev_v1_1.py` | 现有启动链；带版本名不代表废弃。 |

## B. 可以删除（执行清单）

| 项目 | 确认依据 / 替代位置 |
| --- | --- |
| `frontend/src/styles.css` 中 19 个无引用旧 class 对应的选择器 | 已检查 TSX、TS、JS、测试及动态 class 拼接；旧示意地图、铁路票卡、空态插画和标签 DOM 已不存在。保留共用规则中仍使用的选择器，使用 CSS AST 删除，避免误伤媒体查询。具体选择器见最终清理记录。 |
| `App.tsx` 中旧 `<nav>` 及仅供它使用的图标 import；相应导航 CSS | 后续全局 `.topbar nav{display:none}` 在全部宽度隐藏该导航；旅行/演示切换是独立可见控件，完整保留。 |
| `.env.example` 的 `RAIL_API_KEY` 空字段及现行配置文档对应说明 | 当前 Mock/Dataset/unsupported RealRail 路径不使用该值。代码中兼容 Settings 字段暂保留，避免改变冻结后端配置合同；本地 `.env` 不改动。 |
| `docs/screenshots/v121-initial.png`、`v121-loading.png` | 早期 UI/加载态草稿；无受 Git 管理的代码、测试或文档引用。最终 V1.2.1、V1.2.2 桌面/移动截图和所有正式验收仍保留。 |
| `.tooling/` 中一次性 `*-edit.py`、已完成 V1.2.2 patch/spec 生成脚本 | 仅改写源文件的开发操作脚本，不是服务、测试或正式 CLI 入口；不再作为当前代码复现依赖。按明确文件清单删除，不递归清空工具目录。 |
| `.tooling/release/`、`.tooling/readme-preview/` | 前次发布检查脚本、diff、HTML 与 SVG 渲染预览；正式报告已在 docs，检查所需逻辑先在本轮 ignored 工作目录保留。 |

## C. 建议保留但可选

- `evals/runner.py`、`compare.py`、旧 24 个 cases：历史评估工具且仍被测试/文档引用，不能仅因已有 50-case runner 就删除。
- `backend/live_check.py`：独立真实 Provider 校验入口，非生产 import，但有实际验证用途。
- 各版本正式截图和验收 JSON：部分没有单独 Markdown 链接，但仍属于对应版本 evidence；只清理明确的两张 UI 草稿。
- `evals/v1_2/development_runs.json`：约 1 KB，正式报告引用的开发成本记录，保留。ignored 中间评测目录与 before 快照可解释历史修复，暂保留，避免丢失原始对照。
- `.tooling` 中历史 LIVE 验证脚本：可复用真实联调且有诊断价值；本轮仅删除一次性改代码脚本。
- `node_modules`、虚拟环境、Node/OpenSpec 工具、构建和测试产物：都被 Git 忽略，保留可运行环境；不会上传。

## D. 不确定，需要谨慎

- `RealRailProvider` / `RealFlightProvider` 是显式 unsupported 边界，factory 和测试会使用；删除会把受控错误变为配置或运行异常，本轮保留。
- `QWEN_MODEL` 是已测试的旧模型名兼容 fallback，首选仍为 `QWEN_CHAT_MODEL`；保留兼容行为，不创建双重配置。
- `Settings.rail_api_key` 无实际请求消费者，属于可选后续 API 合同清理。本轮从示例去掉，但不修改已冻结的后端模型。
- 同名 `core/budget.py` / `harness/budget.py`、旧/新 evaluator 不是可互换重复模块；分别服务兼容入口/统一运行预算与不同历史评测口径。保留，不抽象重构。

## 依赖与风格结论

Python 以 `requirements.in` 的直接依赖为起点，读取已安装 metadata，按当前平台和 extras 展开完整依赖链；`requirements.txt` 所有条目均可达，未发现可删除孤立包。`uvicorn[standard]` 和 `a2a-sdk[http-server]` 的间接依赖不是垃圾。前端 3 个运行依赖及 6 个开发依赖均有源码、构建、类型或浏览器测试用途。无必要改写锁文件，无版本升级。

未发现 QueryMate / LifeOps 残留，应用源码无 TODO/FIXME、调试 print 或 console.log。CLI runner、启动器及 LIVE smoke 的输出是进度/结果接口，需保留。未发现应整体删除的重复 Provider、废弃 React 组件或大型注释代码块；不为减少行数重构稳定逻辑。

## 验证与实际清理结果

- 删除 32 个文件，共 7,059,018 字节（约 6.73 MiB）：2 张受 Git 管理的截图草稿、30 个被忽略的本地临时文件。不是删除 32 个产品模块。完整相对路径见[清理与验证记录](final-clean-checks.json)。
- CSS 删除 58 处选择器（含媒体查询中的重复选择器），涉及 20 个旧 class；源码从 34,022 字节降至 29,812 字节，减少 4,210 字节。仅移除旧 DOM 对应的样式，共用规则中的有效选择器保留。
- 删除始终隐藏的旧导航及其独占图标 import；旅行/演示模式、页面功能和现存 React 组件全部保留。另移除 `.env.example` 的无消费者空字段 `RAIL_API_KEY` 及配置文档对应说明；本地 `.env` 未改动。
- 未找到可安全删除的孤立依赖、重复 Provider 或废弃业务模块；Python/npm 依赖和锁文件不变，不升级版本。
- `backend/`、正式 tests、evals 和 OpenSpec 内容均未修改；31 个正式评测/基线文件逐一比对审计起点，全部相同；manifest 冻结的 71 个实现与数据文件也全部相同。
- 重新离线汇总两版 200 条原始结果：历史 TripPilot 44/50、最终 48/50，两版 Baseline 均为 32/50，指标与原 summary 一致。没有重跑 50+50 付费 Benchmark。

### 完整回归

| 检查 | 本轮结果 |
| --- | --- |
| `PYTHONPATH=.:backend backend/.venv/bin/pytest backend/tests -q` | 215 passed，0 failed；1 条第三方弃用警告。包含 MCP、A2A HTTP 集成、Harness、Memory、Hotel、Flight、evaluator 和语义校验。 |
| `npm --prefix frontend test` | 1 passed，0 failed。 |
| `playwright test --config frontend/playwright.config.ts --workers 1` | 24 passed，0 failed；最终地图调整后重跑。测试生成的历史截图恢复原内容，避免覆盖既有证据。 |
| `backend/.venv/bin/ruff check backend evals scripts` | All checks passed。 |
| `npm --prefix frontend run build` | TypeScript / Vite 通过；最终地图调整后重跑。 |
| `openspec validate --all --strict` | 6 passed，0 failed。 |

### 当前真实运行与限制

主后端 8000、MCP 8200、Transport A2A 8101、Local Travel A2A 8102 和前端 5173 均在本地运行；复用现有服务，前端加载修改后的代码。入口为 `http://127.0.0.1:5173`。本轮[真实浏览器记录](final-clean-live-check.json)验证旅行/演示模式、行程、酒店、交通比较、偏好控件、安全执行摘要和实际高德 SDK；未改写用户 SQLite 偏好。

- Qwen `qwen-plus` LIVE、Amap LIVE、Hotel Amap POI LIVE；Rail / Flight DATASET。
- MCP 实际发现 **7 个 tools**，**2 个 A2A 服务** ONLINE；Harness / Memory ACTIVE。
- 五天三城行程确实生成，经历 Critic 和 1 次有界重规划；南京 Day 3 市内交通为 123 分钟、上限 120，最终状态为 `conflict`，保留 2 条同一交通问题相关的 confirmed/blocking 校验结果。没有把它写成 Critic Pass，也没有静默切 Mock。
- 北京→上海三天案例展示铁路/航班比较及真实酒店候选，状态 `partial`、Critic valid、无确认阻塞；未知价格/天气等仍待确认。
- 两个案例的浏览器 console / page error / HTTP error 均为 0。主服务及三个协议服务日志无 ERROR/CRITICAL、Traceback 或 HTTP 5xx。
- `integration_passed` 只表示链路与展示通过，不表示所有行程满足全部约束；`all_plans_critic_valid=false` 明确保留。

### 安全与发布边界

当前可上传文件、所有可达 Git 历史对象、`.tooling` 日志均进行内存凭据匹配和通用模式扫描，无命中；36 张保留截图通过本地 Tesseract OCR 匹配，无命中，无识别失败，不保留 OCR 原文。当前文本文件未发现用户本机绝对路径。模式扫描不是对任意未知秘密的数学保证；本轮未发现泄露。

`.env`、`.env.local`、`.env.*.local`、SQLite 和工具目录均被 Git 忽略；`.env` 未跟踪，`.env.example` 保持空占位且可上传。真实凭据只在本地内存中用于授权调用和扫描，不写入验收材料。

README 保留简洁展示结构，新增最终审计入口并同步真实测试计数。[最终简历核验](resume-claim-audit-final.md)共 28 项：SUPPORTED 28、PARTIAL 0、NOT SUPPORTED 0；原始历史审计不覆盖。同步前 GitHub 仓库实际为 **public**，保持现有可见性，不修改设置；本地/远程无分叉，V0.2 与 V1.1 checkpoint 保留，不改写历史。

### 验收中发现的已有显示问题

真实五天行程的 Day 4 长 POI 名称出现裁切；回放同一份真实结果，对比清理前后 CSS，标签边界完全相同，确认不是删除旧 CSS 引入。依据[高德官方接口说明](https://developer.amap.com/api/javascript-api-v2/guide/map/state)，`setFitView` 参数顺序为上、下、左、右。`LiveMap.tsx` 仅把左右留白由 65/35 调至 85/85，上下保持 80/35；保留既有地图接口和行为，不改后端或 Benchmark。

修正后使用保存的真实结果与实际 SDK，在 1440 / 390 两个宽度逐日复验，**10/10** 名称、Marker 数量和完整视野检查通过，console / page error 均为 0。原始失败和后续复验分别保留；这次回放不算新的端到端模型规划。
