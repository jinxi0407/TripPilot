# 评估证据

`manifest.json` 标识本项目编写的合成证据版本。POI 坐标仅用于示意，开放时间、车次、票价、天气和路线时长均为合成测试数据，不是实际出行信息。

共享证据源：`backend/app/providers/fixtures.py`、`backend/app/providers/amap.py` 的 Mock adapter 和 `backend/app/providers/data/rail.json`。用例通过 `fixture_overrides` 明确注入天气、费用或错误草案，校验器必须发现并反馈；并非替换成预先写好的最终结果。每个报告保存这些证据文件的 SHA-256。

01–20 为规划/验证案例，21–24 为故障控制案例。`runner.py` 会区分纯系统运行和注入的错误草案，并记录每轮 Critic 的问题类型。通过用例只代表预期行为被观测到，不代表真实模型质量。
