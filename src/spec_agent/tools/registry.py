"""工具定义、注册、参数校验与安全分发。"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar, cast

from pydantic import BaseModel, ValidationError

from spec_agent.models import ToolCall, ToolError, ToolResult

ArgsT = TypeVar("ArgsT", bound=BaseModel)
_TOOL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


@dataclass(frozen=True)
class ToolDefinition:
    """已注册的工具及其参数模型和执行函数。"""

    name: str
    description: str
    args_model: type[BaseModel]
    execute: Callable[[BaseModel], str]


class ToolRegistry:
    """管理工具定义并在执行前校验不可信参数。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        args_model: type[ArgsT],
        func: Callable[[ArgsT], str],
    ) -> None:
        """注册一个工具；同名工具或无效定义会显式报错。"""
        if not _TOOL_NAME_PATTERN.fullmatch(name):
            raise ValueError(
                "工具名称必须以小写字母开头，且只能包含小写字母、数字、连字符和下划线"
            )
        if not description.strip():
            raise ValueError("工具描述不能为空")
        if name in self._tools:
            raise ValueError(f"工具名称已注册：{name}")

        def execute(validated_args: BaseModel) -> str:
            return func(cast(ArgsT, validated_args))

        self._tools[name] = ToolDefinition(
            name=name,
            description=description.strip(),
            args_model=args_model,
            execute=execute,
        )

    def schemas(self) -> list[dict[str, object]]:
        """导出适用于 OpenAI 兼容工具调用接口的 JSON Schema 描述。"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.args_model.model_json_schema(),
                },
            }
            for tool in self._tools.values()
        ]

    def dispatch(self, call: ToolCall) -> ToolResult:
        """校验并执行工具调用，将调用错误转成结构化结果。"""
        tool = self._tools.get(call.name)
        if tool is None:
            return ToolResult(
                tool_call_id=call.id,
                name=call.name,
                success=False,
                error=ToolError(
                    code="unknown_tool",
                    message=f"未注册名为“{call.name}”的工具",
                ),
            )

        try:
            validated_args = tool.args_model.model_validate(call.arguments)
        except ValidationError as exc:
            details = "; ".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors(include_input=False, include_url=False)
            )
            return ToolResult(
                tool_call_id=call.id,
                name=call.name,
                success=False,
                error=ToolError(
                    code="invalid_arguments",
                    message=f"工具参数校验失败：{details}",
                ),
            )

        try:
            content = tool.execute(validated_args)
        except Exception:
            return ToolResult(
                tool_call_id=call.id,
                name=call.name,
                success=False,
                error=ToolError(
                    code="tool_execution_error",
                    message="工具执行失败",
                ),
            )

        return ToolResult(
            tool_call_id=call.id,
            name=call.name,
            success=True,
            content=content,
        )
