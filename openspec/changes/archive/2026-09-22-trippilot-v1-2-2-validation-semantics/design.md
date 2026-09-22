# Design

## Context
旧Issue只有low/medium/high，没有status/blocking/目标；check(None)用medium，但合并消息与高风险类型使展示混淆；缺少交通选项直接检查False；预算把所有估算当作已确认费用；低质量/路线提示也触发replanning。先保存同日期真实before，再变更。

## Goals / Non-Goals
**Goals:** 明确三类语义、只对确认硬冲突重规划、保留数据缺口、按旅行任务聚合、同题同配置重新测评。
**Non-Goals:** 不增加功能/Agent，不重构协议或工作流，不改ground truth，不覆盖旧测评。

## Decisions
- Issue: type, severity(info/warning/error), status(confirmed/unverified/informational), blocking, day, activity_id, target, source, evidence；保留observed/allowed/evidence_ids。约束blocking必须是confirmed+error。
- check(True)通过；None为unverified且非阻塞；False硬事实为confirmed/error/blocking，软建议为非阻塞informational。valid仅表示无blocking，不表示信息全部已验证。
- 未知交通覆盖只报告TRANSPORT_UNVERIFIED；已有匹配候选而未选中是可修复的已确认关联缺陷，不伪造交通。检查候选的城市/日期与day关联。
- 费用保留兼容字段；known_cost不含estimate占位，estimated_cost含估算，unknown_cost_items保留未取得的费用。仅known_cost超预算阻塞，估算超预算为BUDGET_RISK。
- 去重以day/type/activity_id或target；天气按city/date，酒店按hotel/route目标。旅行UI按类别聚合，不删除技术详情。
- Critic gate只看blocking，保留现有最多2次调整与所有超时/预算；记录有界validation_history，仅包含校验快照和是否请求重规划，无模型推理。
- completed无blocking且无unverified；partial无blocking但有unverified；conflict存在confirmed blocking。执行限制仍保留安全错误与partial，不能假装正常完成。
- 新evals/v1_2_2读取原50-case，使用相同Qwen、温度、Provider fixture、协议与执行预算；baseline同配置。旧目录不动，新evaluator改用blocking并严格记录冲突→Critic→replan→消除的链路。未知且未重规划不纳入分母，未出现可评估冲突为N/A。
- 两天范围：先复现/语义/测试，再UI/LIVE与完整测评。正式测评前冻结backend/evaluator，任何影响结果的修复须保存旧尝试后全量重跑。

## Risks / Trade-offs
未知不是不可行，也不是已证明可行；partial必须保留。新语义可能降低某些成功率或重规划样本数，完整报告，不调整标签。实际模型调用有成本，本轮用户已明确授权100题；使用原有总调用/时间/token上限。
