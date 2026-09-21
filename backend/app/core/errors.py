from pydantic import BaseModel

MESSAGES = {
    "AUTH_REQUIRED": "实时服务未配置或认证失败，请检查环境变量。",
    "TIMEOUT": "外部服务响应超时，请稍后重试。",
    "RATE_LIMITED": "外部服务请求限流，请稍后重试。",
    "UNSUPPORTED": "当前服务不支持此查询。",
    "INVALID_INPUT": "输入内容不符合要求。",
    "INVALID_OUTPUT": "服务返回的数据不符合结构要求。",
    "PROVIDER_FAILURE": "外部服务暂时不可用。",
    "TOOL_DENIED": "当前智能体没有此工具的访问权限。",
    "DUPLICATE_ACTION": "重复失败的工具调用已停止。",
    "DEADLINE_EXCEEDED": "本次规划已达到时间限制。",
    "BUDGET_EXHAUSTED": "本次执行已达到调用次数限制。",
    "MAX_STEPS": "规划已达到最大执行步数。",
    "CANCELLED": "本次规划已取消。",
    "CAPACITY": "当前规划任务较多，请稍后重试。",
    "NOT_FOUND": "任务不存在或已过期，请重新提交。",
    "CONFLICT": "任务状态或版本已变化，请刷新后重试。",
    "GRAPH_LIMIT": "工作流已达到安全执行上限。",
}


class SafeError(BaseModel):
    code: str
    message: str
    retryable: bool = False
    provider_code: str | None = None


class ControlledError(Exception):
    def __init__(self, code: str, retryable: bool = False, provider_code: str | None = None) -> None:
        self.error = SafeError(
            code=code,
            message=MESSAGES.get(code, MESSAGES["PROVIDER_FAILURE"]),
            retryable=retryable,
            provider_code=provider_code
            if provider_code and provider_code.isdigit() and len(provider_code) == 5
            else None,
        )
        super().__init__(self.error.message)
