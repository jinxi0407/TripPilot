# TripPilot V1.2 录屏演示（约 5–7 分钟）

先按 README 用 `./scripts/dev_v1_2.sh` 启动四个后端服务，再单独启动前端，打开 `http://127.0.0.1:5173`。按 README 配置本地凭据后，选择「Qwen · 需配置模型」运行 LIVE Demo；普通单元与浏览器回归仍使用 Mock。不要在录屏中打开 `.env`、SDK 请求 URL 或网络凭据。

1. **提出需求**：展示左侧三城五天、4000 元、历史和夜景的自然语言需求。点击「三城慢游 · 历史与夜色」。说明一键 Demo 使用铁路 Dataset 的固定日期：2026-10-10 起五天，不代表实时车次或余票。
2. **展示工作流**：指出 Supervisor → A2A Transport / Local Travel → MCP search_rail / search_poi → Rail Dataset / Amap LIVE → Travel Planner ReAct → Critic。展示 MCP CONNECTED、A2A 2/2 ONLINE、Harness ACTIVE，悬停查看工具和预算。展开「执行记录」，展示工具查询、Observation 后的动作和最终校验；这些是安全摘要，不是隐藏推理。
3. **解释结果**：切换 Day 1–5，展示车站和时刻、景点、当地交通耗时、每日费用与六类总预算。指出 Qwen LIVE、Amap LIVE、Rail DATASET 和“余票未确认”。当前真实预报不覆盖 Demo 日期，门票、开放时间也有未知项，因此“部分待确认”是诚实结果，不要描述为全部出行约束均已证实。
4. **应对天气**：点击「模拟暴雨 · 重规划」，观察新版本和 Critic 反馈；新版活动改为室内，并重新校验路线。页面明确提示这是用户模拟暴雨，高德 POI 和路线仍来自真实查询。
5. **展示不可能约束**：把总预算改为 `200` 元，点击「重新规划」。展示明确的预算冲突，以及自动修复有次数上限，不会为了给出“成功”而修改用户预算。
6. **讲清边界**：右侧为高德真实底图，当天 Marker、名称及视野随日期更新；不提供复杂导航。铁路为 Dataset，住宿与餐饮为预算估算，未知费用不会按零处理。

如要重置演示，直接再次点击 Demo 卡片。普通提交不填日期时，会先要求补充。

Provider 故障复现可通过 API 提交：

```sh
curl -s http://127.0.0.1:8000/api/plan \
  -H 'Content-Type: application/json' \
  -d '{"query":"10月10日杭州一日游。","mode":"fixture","scenario":"outage"}'
```

随后访问返回的 `poll_url`。浏览器 E2E 用相同的 scenario 验证 UI 提示；[故障截图](screenshots/provider-outage.png) 是实际运行结果。

不要声称：真实订票、真实余票保障、所有景点开放时间都已验证、实时模型性能提升，或已部署生产级分布式平台。可以展示的工程能力包括 LangGraph 状态图、Tool Registry、Pydantic 合同、ReAct 上限、Provider 替换、确定性 Critic、动态重规划，以及经真实本地协议集成和 LIVE E2E 验证的 MCP、A2A、Runtime Harness。

没有 Key 的环境可显式选择「Mock · 无需 API Key」演示，必须保留模拟标签；不能将 Mock 截图当作 LIVE 证据。最新验收见 [V1.2.2 报告](v1.2.2-validation-report.md)；历史 V1.2 验收结果见 [V1.2 报告](v1.2-validation-report.md)；[V1.1 报告](v1.1-validation-report.md)，[V0.2 历史报告](v0.2-live-report.md) 保留。

## V1.1 MCP 真实超时降级演示

启动器输出当前 MCP PID；只对本次启动的 MCP 进程操作。另开终端执行 `kill -STOP <当前MCP_PID>`，再在前端选择 LIVE 并运行五天 Demo。等待真实超时和重试后，应看到 `MCP FALLBACK`、安全 Trace 中的 TIMEOUT/RETRY/FALLBACK，以及真实 Provider 返回的行程。本机本次耗时约122秒，仍受180秒总预算限制。

完成后务必执行 `kill -CONT <同一个MCP_PID>` 恢复，再查看 `/health` 的 MCP CONNECTED；若演示中断也要恢复。不要直接关闭还处于暂停状态的服务终端。自动验收使用 `try/finally` 保证恢复。此过程只模拟 MCP 连接失效，不替换 Qwen/高德数据；已有运行的 FALLBACK 标签保留，新的健康探测不会篡改旧运行记录。


## V1.2 产品能力与评估

1. 展开 **Travel Preferences · 旅行偏好**，选慢游、历史、夜景、避免早班和近地铁，勾选「记住我的偏好」后保存。它只写入本机 SQLite 的结构化字段，不保存整段聊天。
2. 新建请求「帮我规划南京三天，预算3000元」，填出发日期 `2026-10-10`；若要求澄清出发地，按南京同城游填写南京。展示 Trace 的「已加载旅行偏好」、Memory ACTIVE，以及兴趣和节奏被保留。近地铁是排序偏好，没有地铁证据的候选仍写未知。用本次明确要求「这次紧凑一些」说明当前请求优先。
3. 运行五天三城 Demo，滚动到当天 **住宿建议**，切换杭州、南京、苏州：推荐区域由实际行程景点生成，展示真实 Amap Hotel POI、地址、距离和已获得的路线。指出未获得路线的候选为待确认，酒店没有实时房价、房态或预订保证。
4. 输入「我想从北京出发去上海玩三天，预算4000元，喜欢历史景点。请比较高铁和飞机的门到门时间，并推荐住宿区域」，日期仍用 `2026-10-10`。在 **Rail vs Flight** 比较班次时刻、接驳、缓冲、线路时长、抵达接驳与费用，明确两种交通都是 Dataset，市中心接驳为估计。
5. 展示 **7 MCP tools / 2 A2A specialists / Harness ACTIVE**。架构保留五个逻辑 Agent，酒店与航空分别归 Local Travel、Transport，没有增加新 Agent。
6. 打开 [50-case Benchmark 报告](../evals/v1_2_2/summary.md)，说明双方使用真实 `qwen-plus`、temperature 0 与相同固定证据。展示实际任务成功、约束满足、工具 F1、延迟/Token 和完整失败列表；不要把固定数据评估说成50次真实出行验证，也不要隐藏失败。

录屏前按验收报告选择已经跑通的路径；真实请求可能因模型或网络产生受控失败。长期偏好可能影响后续演示，不需要时用「清除偏好」。新旅行需求会更新目的地；“第二天不要户外”或独立“预算改为200元”才续接当前行程。演示结束不需要继续增加功能。

V1.2 历史 LIVE 实测：五场景集成通过，但暴雨后的Critic自动重规划由酒店绕路风险触发。录屏可展示室内替换、酒店重选与Critic校验，不要把这段Trace讲成已观测到“天气冲突触发Critic”。当时旧口径的重规划 Benchmark 结果为 1/10；V1.2.2 按实际确认冲突定义的严格恢复为 1/3，两种分母不能直接比较。未知酒店路线在当前版本不会触发重规划。

## V1.2.2 最终演示口径

默认旅行模式只显示辅助旅行信息；切换演示模式再展示 Provider、协议与 Harness。未来天气显示“天气待临近出发确认”；0 个 confirmed conflict 时，绿色/中性横幅与待确认清单可以同时出现。不要为了录屏要求模型把 unknown 改成已验证。无确认冲突时预算/路线修复按钮按条件隐藏；调整预算可直接输入“预算改为200元”，以实际运行的 Critic 结果为准。

最新真实五天结果为 partial，0 个确认冲突、18 条待验证、2 条提示，无自动重规划。[真实前后记录](v122-before-after.json) 未复现旧版误触发，因此不要把语义和显示优化讲成已经观测到的错误重规划修复。
