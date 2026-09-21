# Tasks

## 1. Phase A — 配置
- [x] 1.1 核对根目录环境加载，只报告配置状态，确认 .env 被忽略。
## 2. Phase B — Qwen
- [x] 2.1 修复真实模型结构化调用并验证成功、实际模型名、超时与重试，不暴露推理。
## 3. Phase C — 高德
- [x] 3.1 验证西湖 POI、杭州天气、正确灵隐景区的距离/路线，保留 amap_live 来源与安全错误码。
## 4. Phase D — 状态
- [x] 4.1 API 和 UI 展示实际 Provider 状态，测试配置齐全不等于 LIVE，失败不冒充 Mock。
## 5. Phase E — 地图
- [x] 5.1 接入 SDK、服务代理、底图、当日 Marker/名称/自动视野，验证密钥不进入日志和失败 fallback。
## 6. Phase F — 修订
- [x] 6.1 实现真实行程上的明确天气模拟及有界重规划，离线验证未知天气和预算冲突。
## 7. Phase G — 完整 Demo
- [x] 7.1 重启本地服务，实际 Qwen/高德/Dataset 完成五天图流程，记录真实完成状态及未知项目。
## 8. Phase H — 场景
- [x] 8.1 真实模型验证暴雨室内替换及 200 元预算不可满足，记录 Trace 和次数。
## 9. Phase I — 浏览器
- [x] 9.1 真实浏览器验证底图、Marker、切换日期、Provider 标签及 console，保存不含凭据的证据。
## 10. Phase J — 回归
- [x] 10.1 后端、前端/浏览器测试、Ruff、build、OpenSpec strict 通过，测试隔离真实 Key。
## 11. Phase K — 报告
- [x] 11.1 更新中文实际验收报告和边界，核对 Git 忽略，无 commit/push。

最终验收：Qwen qwen-plus、高德 Web Service 与真实 JS 底图/Marker 已成功；五天流程及暴雨修订保留 partial（已知约束 valid=true，未知数据未伪造），200 元返回 conflict。Chrome 实际三场景通过且 console/page error 均为 0。Backend 117、Frontend 1、离线 Browser 6 项通过。详细证据见 docs/v0.2-live-report.md。未 commit、push 或归档。
