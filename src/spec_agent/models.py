"""供 Agent 各组件共享且经过校验的数据契约。"""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

MessageRole = Literal["system", "user", "assistant", "tool"]
TraceEventType = Literal[
    "user_message",
    "model_response",
    "tool_call",
    "tool_result",
    "error",
    "max_iterations",
]


class ContractModel(BaseModel):
    """不可变的数据契约基类，拒绝未声明的字段。"""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ToolCall(ContractModel):
    """由模型提出的工具调用；参数属于不可信输入。"""

    id: str
    name: str
    arguments: dict[str, JsonValue]


class Message(ContractModel):
    """与模型或工具交互的会话消息。"""

    role: MessageRole
    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None

    @model_validator(mode="after")
    def validate_tool_message(self) -> "Message":
        if self.role == "tool" and not self.tool_call_id:
            raise ValueError("工具消息必须包含 tool_call_id")
        if self.role != "assistant" and self.tool_calls:
            raise ValueError("只有 assistant 消息可以包含 tool_calls")
        return self


class ModelResponse(ContractModel):
    """模型响应，可包含文本、工具调用或两者。"""

    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()

    @model_validator(mode="after")
    def require_response_content(self) -> "ModelResponse":
        if self.content is None and not self.tool_calls:
            raise ValueError("模型响应必须包含文本或至少一个工具调用")
        return self


class ToolError(ContractModel):
    """安全且结构化的工具错误。"""

    code: str
    message: str


class ToolResult(ContractModel):
    """工具调用的执行结果。"""

    tool_call_id: str
    name: str
    success: bool
    content: str | None = None
    error: ToolError | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> "ToolResult":
        if self.success and self.error is not None:
            raise ValueError("成功的工具结果不能包含错误")
        if not self.success and self.error is None:
            raise ValueError("失败的工具结果必须包含错误")
        return self


class TraceEvent(ContractModel):
    """执行追踪中的带时间戳、非敏感事件。"""

    event_type: TraceEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    data: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def require_timezone_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("追踪事件的时间戳必须包含时区")
        return value
