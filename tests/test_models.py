"""Contract model tests, executed with stest."""

from datetime import datetime

from pydantic import ValidationError
from stest import AbstractTestCase, Test

from spec_agent.models import (
    Message,
    ModelResponse,
    ToolCall,
    ToolError,
    ToolResult,
    TraceEvent,
)


class ModelsTest(AbstractTestCase):
    @Test(priority=1, enabled=True, name="工具调用参数需为有效 JSON")
    def tool_call_accepts_json_arguments(self) -> None:
        call = ToolCall(
            id="call-1",
            name="calculator",
            arguments={"expression": "2 + 3", "options": {"precision": 2}},
        )

        self.assertEqual(call.name, "calculator")
        self.assertEqual(call.arguments["expression"], "2 + 3")

    @Test(priority=2, enabled=True, name="只有助手消息可以包含工具调用")
    def user_message_rejects_tool_calls(self) -> None:
        call = ToolCall(id="call-1", name="calculator", arguments={})

        with self.assertRaises(ValidationError):
            Message(role="user", content="calculate", tool_calls=(call,))

    @Test(priority=3, enabled=True, name="模型响应必须包含文本或工具调用")
    def model_response_rejects_empty_response(self) -> None:
        with self.assertRaises(ValidationError):
            ModelResponse()

    @Test(priority=4, enabled=True, name="工具执行失败时必须提供结构化错误")
    def failed_tool_result_requires_error(self) -> None:
        with self.assertRaises(ValidationError):
            ToolResult(
                tool_call_id="call-1",
                name="calculator",
                success=False,
            )

        result = ToolResult(
            tool_call_id="call-1",
            name="calculator",
            success=False,
            error=ToolError(code="invalid_arguments", message="Invalid expression"),
        )
        self.assertFalse(result.success)

    @Test(priority=5, enabled=True, name="轨迹事件时间戳必须包含时区")
    def trace_event_rejects_naive_timestamp(self) -> None:
        with self.assertRaises(ValidationError):
            TraceEvent(event_type="user_message", timestamp=datetime(2026, 1, 1))
