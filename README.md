# spec-agent-lab

一个用于学习 Agent 核心循环的 Python 教学项目。项目采用规范驱动开发，先定义需求、设计和任务，再逐步实现模型交互、工具、上下文、技能与本地检索。

当前实现进度以 [tasks.md](./tasks.md) 为准。

## 环境要求

- Python 3.11 或更高版本
- pip

## 安装开发依赖

在项目根目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

项目目前使用 Pydantic v2 定义核心数据模型；自动化测试使用 [stest](https://github.com/hotswwkyo/stest)。

## 验证

```powershell
python -m stest discover -s tests -p "*.py"
ruff check .
mypy --strict src/
```

stest 测试类继承 `AbstractTestCase`，测试方法使用 `@Test(...)` 标记。完整功能示例将在后续任务中添加。

