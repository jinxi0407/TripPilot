# Tasks

## 1. Phase A — 基线与规格
- [x] 1.1 扫描凭据并创建 V0.2 checkpoint，切换目标分支；git log/status 和忽略检查确认。
- [x] 1.2 完成 proposal/design/spec/tasks，运行 V1.1 strict validation 后才开始实现。
## 2. Phase B — SDK 与配置
- [x] 2.1 安装并 pin 官方稳定 MCP/A2A SDK，pip check 和实际版本检查通过，集中配置端口与策略。
## 3. Phase C — Harness
- [x] 3.1 实现统一 policy、预算、步骤、deadline、外部调用与委派额度；真实逻辑单元测试覆盖边界与失败计数。
- [x] 3.2 将白名单、重复保护、重试、schema、fallback 与安全 trace 接入 Registry/模型/ReAct/Critic；原117项回归通过。
## 4. Phase D — MCP
- [x] 4.1 实现独立 Streamable HTTP server/client 五工具，复用 Provider；真实 discovery/invocation/schema 集成测试通过。
- [x] 4.2 实现 MCP timeout/retry/离线 fallback 与实际状态；故障测试证明不伪造连接或来源。
## 5. Phase E — A2A
- [x] 5.1 独立专家 Cards 和标准任务/产物，真实 discovery、技能验证、两专家调用与 MCP 链测试通过。
- [x] 5.2 主图接入 A2A，验证类型化 state delta、取消/timeout、预算结算与 A2A FALLBACK。
## 6. Phase F — 可观测性
- [x] 6.1 health/运行 API/UI 显示实际 MCP、A2A、Harness 与安全协议 trace；离线和浏览器状态测试通过。
## 7. Phase G — 启动
- [x] 7.1 提供本地一命令服务启动/清理，默认端口8000/8101/8102/8200，实际启动及健康检查通过。
## 8. Phase H — LIVE 场景
- [x] 8.1 实测真实 Qwen/Amap/A2A/MCP 五天、暴雨、200元场景，保留 partial/冲突和实际协议证据。
- [x] 8.2 暂停真实 MCP 进程至超时后实测 fallback Demo，trace 明确降级且结果有真实来源；恢复服务。
## 9. Phase I — 回归
- [x] 9.1 全部 backend/Harness/MCP/A2A、frontend/browser、Ruff/build/OpenSpec strict 通过并记录实测数量。
## 10. Phase J — 安全与兼容
- [x] 10.1 检查浏览器 console、服务日志、未跟踪/变更文件和构建产物无凭据；旧 change 无修改，checkpoint 保留。
## 11. Phase K — 文档
- [x] 11.1 更新架构、启动、协议/运行边界和实测报告，仅在真实集成与 E2E 通过后写简历能力声明；不 push/merge。
