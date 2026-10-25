"""项目内置的受控工具。"""

import ast
import math
import operator
from collections.abc import Callable
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from spec_agent.tools.registry import ToolRegistry

_MAX_EXPRESSION_LENGTH = 256
_MAX_AST_NODES = 64
_MAX_ABS_RESULT = 1e100

_BINARY_OPERATORS: dict[type[ast.operator], Callable[[int | float, int | float], int | float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_UNARY_OPERATORS: dict[type[ast.unaryop], Callable[[int | float], int | float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


class CalculatorArgs(BaseModel):
    """计算器工具的输入参数。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    expression: str = Field(
        min_length=1,
        max_length=_MAX_EXPRESSION_LENGTH,
        description="仅支持数字、括号及加减乘除运算符的算术表达式",
    )


class _ExpressionEvaluator(ast.NodeVisitor):
    """仅解释数字常量和白名单算术运算符。"""

    def __init__(self) -> None:
        self._visited_nodes = 0

    def evaluate(self, expression: str) -> int | float:
        tree = ast.parse(expression, mode="eval")
        result = self.visit(tree)
        if type(result) not in (int, float):
            raise ValueError("表达式结果必须是实数")
        if not math.isfinite(result) or abs(result) > _MAX_ABS_RESULT:
            raise ValueError("表达式结果超出允许范围")
        return result

    def visit(self, node: ast.AST) -> int | float:
        self._visited_nodes += 1
        if self._visited_nodes > _MAX_AST_NODES:
            raise ValueError("表达式过于复杂")
        return cast(int | float, super().visit(node))

    def generic_visit(self, node: ast.AST) -> int | float:
        raise ValueError(f"不支持的表达式元素：{type(node).__name__}")

    def visit_Expression(self, node: ast.Expression) -> int | float:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> int | float:
        if type(node.value) not in (int, float):
            raise ValueError("表达式只允许使用数字")
        return cast(int | float, node.value)

    def visit_BinOp(self, node: ast.BinOp) -> int | float:
        operation = _BINARY_OPERATORS.get(type(node.op))
        if operation is None:
            raise ValueError("只支持加、减、乘、除运算")
        left = self.visit(node.left)
        right = self.visit(node.right)
        return operation(left, right)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> int | float:
        operation = _UNARY_OPERATORS.get(type(node.op))
        if operation is None:
            raise ValueError("只支持正负号")
        return operation(self.visit(node.operand))


def calculator(args: CalculatorArgs) -> str:
    """计算安全算术表达式并返回结果文本。"""
    try:
        result = _ExpressionEvaluator().evaluate(args.expression)
    except (SyntaxError, ValueError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError(f"无效的算术表达式：{exc}") from exc
    return str(result)


def register_builtin_tools(registry: ToolRegistry) -> None:
    """将项目内置工具注册到给定注册表。"""
    registry.register(
        name="calculator",
        description="计算只包含数字、括号及加减乘除运算符的算术表达式",
        args_model=CalculatorArgs,
        func=calculator,
    )
