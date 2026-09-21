from pydantic import BaseModel, ConfigDict, Field


class RuntimePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_react_steps: int = Field(default=8, ge=1, le=20)
    max_replanning_attempts: int = Field(default=2, ge=0, le=5)
    max_tool_calls: int = Field(default=40, ge=1, le=200)
    max_model_calls: int = Field(default=30, ge=1, le=100)
    max_external_calls: int = Field(default=160, ge=1, le=500)
    total_timeout_seconds: float = Field(default=180, gt=0, le=600)
    react_timeout_seconds: float = Field(default=90, gt=0, le=300)
    tool_timeout_seconds: float = Field(default=10, gt=0, le=60)
    model_timeout_seconds: float = Field(default=30, gt=0, le=120)
    a2a_timeout_seconds: float = Field(default=60, gt=0, le=180)
    mcp_timeout_seconds: float = Field(default=15, gt=0, le=60)
    health_timeout_seconds: float = Field(default=3, gt=0, le=10)
    max_retries: int = Field(default=1, ge=0, le=3)
    duplicate_call_threshold: int = Field(default=2, ge=1, le=5)
    transport_tool_allowance: int = Field(default=6, ge=1, le=40)
    local_tool_allowance: int = Field(default=30, ge=1, le=100)
