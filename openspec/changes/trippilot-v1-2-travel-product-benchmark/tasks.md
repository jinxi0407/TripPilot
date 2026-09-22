# Tasks

## 1. Phase A — 安全与规格
- [x] 1.1 扫描工作区和staged凭据、确认.env忽略、创建V1.1 checkpoint与V1.2分支，git核对两个检查点保留。
- [x] 1.2 完成proposal/design/两个spec/tasks并在代码实现前通过OpenSpec strict。
## 2. Phase B — Memory
- [x] 2.1 实现类型化偏好与SQLite save/load/update/clear/remember=false；测试畸形数据和不保存原文。
- [x] 2.2 实现有界Session上下文、日序修订和严格优先级，接入State/API；测试续轮、覆盖、隔离与修订历史。
## 3. Phase C — Hotel
- [x] 3.1 复用Amap请求层实现HotelProvider及fixture，测试schema/缺失/来源/无假价格/失败处理。
- [x] 3.2 实现行程区域、POI距离及车站路线评分，Critic一次重选受总上限；测试过远/绕路/接驳与重选。
## 4. Phase D — Flight
- [x] 4.1 实现FlightProvider/Dataset/Real接口和固定数据；测试时刻、价格缺失、不可用与provenance。
- [x] 4.2 实现铁路航空分项门到门与偏好排序，接入行程与Critic；测试接驳/缓冲/换乘/早班/合理备选。
## 5. Phase E — 协议与运行
- [x] 5.1 MCP真实发现7工具并调用酒店/航班；A2A两专家扩展Artifact/State，真实本地协议测试通过。
- [x] 5.2 保留Harness/ReAct保护并核对新增工具预算与实际Provider/Memory状态；原回归通过。
## 6. Phase F — 前端
- [x] 6.1 增量加入偏好保存/清除、会话续轮、住宿与交通比较卡片、来源标签；前端与浏览器测试验证。
## 7. Phase G — Benchmark定义
- [x] 7.1 固定恰好50题、五类各10并审核完整标签/唯一性/可满足性；保存数据质量检查与指纹。
- [x] 7.2 实现客观evaluator全指标及百分点比较；测试成功/正确拒绝/未知/伪造来源/分母和工具指标。
- [x] 7.3 实现公平Single-Agent、相同模型/证据/工具；有界runner逐例落盘/resume/安全guard测试通过。
## 8. Phase H — 实测
- [x] 8.1 完成50 TripPilot + 50 Baseline真实qwen-plus/固定Provider运行，保存完整results/summary/失败列表和限制；通用修复后全量重跑。
- [x] 8.2 额外执行10类Harness故障，保存检测/恢复/fallback/安全失败真实计数与原因。
## 9. Phase I — LIVE与演示
- [x] 9.1 Benchmark后运行5个真实LIVE smoke并验证Memory南京/住宿/北京上海及原正常/暴雨/预算六类Demo，保存真实证据与console检查。
## 10. Phase J — 完整回归安全
- [x] 10.1 跑全backend/MCP/A2A/Harness/Memory/Hotel/Flight/evaluator、frontend/browser、Ruff/build/strict，报告新总数与日志。
- [x] 10.2 扫描凭据、SQLite忽略、结果与日志安全、旧changes未改，保留Git检查点；不push/merge。
## 11. Phase K — 最终文档
- [x] 11.1 README/Benchmark表格/resume_metrics与完整中文验收报告只含真实测量，列全部失败和限制；交付后停止功能开发。

验收边界：主评估44/50 vs 32/50，严格天气重规划1/10；5/5 LIVE集成通过，暴雨后室内替换通过，但本次LIVE自动重规划由酒店绕路触发，不能当成天气触发Critic路径证据。完整限制与全部失败见最终报告。
