"""工具注册表与内置计算器测试。"""

from pydantic import BaseModel, Field, ValidationError
from stest import AbstractTestCase, Test

from spec_agent.models import ToolCall
from spec_agent.tools.builtin import CalculatorArgs, calculator, register_builtin_tools
from spec_agent.tools.registry import ToolRegistry


class AddArgs(BaseModel):
    left: int = Field(ge=0)
    right: int = Field(ge=0)


def calculator_code_execution_syntax_data(
    test_class_name: str,
    test_method_name: str,
) -> list[str]:
    return [
        "__import__('os').system('whoami')",
        "open('secret.txt').read()",
        "x + 1",
        "2 ** 100",
        "[1, 2, 3]",
    ]


class ToolRegistryTest(AbstractTestCase):
    @Test(priority=1, enabled=True, name="注册表可导出已注册工具的参数 schema")
    def schema_contains_name_description_and_parameters(self) -> None:
        registry = ToolRegistry()
        registry.register(
            name="add",
            description="将两个非负整数相加",
            args_model=AddArgs,
            func=lambda args: str(args.left + args.right),
        )

        schemas = registry.schemas()
        function_schema = schemas[0]["function"]
        self.assertEqual(function_schema["name"], "add")
        self.assertEqual(function_schema["description"], "将两个非负整数相加")
        self.assertIn("properties", function_schema["parameters"])

    @Test(priority=2, enabled=True, name="注册表拒绝重复工具名称")
    def duplicate_name_is_rejected(self) -> None:
        registry = ToolRegistry()
        registry.register("add", "相加", AddArgs, lambda args: str(args.left + args.right))

        with self.assertRaises(ValueError):
            registry.register("add", "再次相加", AddArgs, lambda args: "0")

    @Test(priority=3, enabled=True, name="成功分发前校验参数并返回结果")
    def dispatch_validates_and_executes_tool(self) -> None:
        registry = ToolRegistry()
        registry.register("add", "相加", AddArgs, lambda args: str(args.left + args.right))

        result = registry.dispatch(
            ToolCall(
                id="call-add",
                name="add",
                arguments={"left": 2, "right": 3},
            )
        )

        self.assertTrue(result.success)
        self.assertEqual(result.content, "5")
        self.assertEqual(result.tool_call_id, "call-add")

    @Test(priority=4, enabled=True, name="非法参数不会执行工具")
    def invalid_arguments_do_not_execute_tool(self) -> None:
        executed = False

        def execute(args: AddArgs) -> str:
            nonlocal executed
            executed = True
            return str(args.left + args.right)

        registry = ToolRegistry()
        registry.register("add", "相加", AddArgs, execute)

        result = registry.dispatch(
            ToolCall(
                id="call-invalid",
                name="add",
                arguments={"left": -1, "right": "秘密值"},
            )
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error.code, "invalid_arguments")
        self.assertFalse(executed)
        self.assertNotIn("秘密值", result.error.message)

    @Test(priority=5, enabled=True, name="未知工具返回结构化错误")
    def unknown_tool_returns_structured_error(self) -> None:
        result = ToolRegistry().dispatch(
            ToolCall(id="call-unknown", name="missing", arguments={})
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error.code, "unknown_tool")

    @Test(priority=6, enabled=True, name="工具执行异常不会泄露异常细节")
    def execution_error_does_not_leak_exception_message(self) -> None:
        def fail(args: AddArgs) -> str:
            raise RuntimeError("敏感内部信息")

        registry = ToolRegistry()
        registry.register("fail", "失败工具", AddArgs, fail)

        result = registry.dispatch(
            ToolCall(
                id="call-failure",
                name="fail",
                arguments={"left": 1, "right": 2},
            )
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error.code, "tool_execution_error")
        self.assertNotIn("敏感内部信息", result.error.message)

    @Test(priority=7, enabled=True, name="工具名称需符合声明格式")
    def invalid_tool_name_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ToolRegistry().register(
                "Calculator",
                "计算工具",
                AddArgs,
                lambda args: str(args.left + args.right),
            )


class CalculatorTest(AbstractTestCase):
    @Test(priority=1, enabled=True, name="计算器支持加减乘除、括号和正负号")
    def calculator_evaluates_arithmetic_subset(self) -> None:
        self.assertEqual(calculator(CalculatorArgs(expression="2 + 3 * (4 - 1)")), "11")
        self.assertEqual(calculator(CalculatorArgs(expression="-8 / 2")), "-4.0")
        self.assertEqual(calculator(CalculatorArgs(expression="+5 - 7")), "-2")

    @Test(
        priority=2,
        enabled=True,
        data_provider=calculator_code_execution_syntax_data,
        name="计算器拒绝任意代码和非白名单语法",
    )
    def calculator_rejects_code_execution_syntax(self, expression: str) -> None:
        with self.assertRaises(ValueError):
            calculator(CalculatorArgs(expression=expression))

    @Test(priority=3, enabled=True, name="计算器拒绝除零和超出范围的结果")
    def calculator_rejects_invalid_or_unbounded_results(self) -> None:
        with self.assertRaises(ValueError):
            calculator(CalculatorArgs(expression="1 / 0"))
        with self.assertRaises(ValueError):
            calculator(
                CalculatorArgs(
                    expression=(
                        "9" * 61
                        + " * "
                        + "9" * 61
                    )
                )
            )

    @Test(priority=4, enabled=True, name="计算器限制表达式长度")
    def calculator_rejects_oversized_expression(self) -> None:
        with self.assertRaises(ValidationError):
            CalculatorArgs(expression="1" * 257)

    @Test(priority=5, enabled=True, name="内置工具注册后可通过注册表调用")
    def builtin_calculator_is_registered_and_callable(self) -> None:
        registry = ToolRegistry()
        register_builtin_tools(registry)

        result = registry.dispatch(
            ToolCall(
                id="call-calculator",
                name="calculator",
                arguments={"expression": "2 + 3"},
            )
        )

        self.assertTrue(result.success)
        self.assertEqual(result.content, "5")
