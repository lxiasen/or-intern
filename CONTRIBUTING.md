# Contributing to OR-Intern

感谢你对 OR-Intern 的贡献兴趣！

## 快速开始

```bash
# 1. Fork 并 clone 仓库
git clone https://github.com/your-username/or-intern.git
cd or-intern

# 2. 安装依赖
uv sync

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 OPENAI_API_KEY

# 4. 运行测试确认环境正常
uv run pytest tests/ -v
```

## 开发流程

### 1. 创建分支

```bash
git checkout -b feature/your-feature-name
```

### 2. 编写代码

- 遵循现有代码风格
- 新工具参考 `AGENTS.md` 中的"添加新工具"指南
- 为新功能添加测试

### 3. 运行测试

```bash
# 全部测试
uv run pytest tests/ -v

# 特定测试文件
uv run pytest tests/unit/test_model_builder.py -v
```

### 4. 提交 PR

- 标题清晰描述改动
- 关联相关 Issue
- 确保 CI 通过

## 代码规范

- **Python 3.10+**，使用 type hints
- **异步优先**：工具 handler 必须是 `async def`
- **错误处理**：工具必须返回友好的错误信息，不能直接抛异常
- **测试覆盖**：每个新工具至少 3 个测试用例

## 工具开发规范

```python
# 1. 定义 tool spec (JSON Schema)
MY_TOOL_SPEC = {
    "name": "my_tool",
    "description": "Tool description for LLM",
    "parameters": {
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "..."},
        },
        "required": ["param1"],
    },
}

# 2. 实现 handler (async, 返回 tuple[str, bool])
async def my_tool_handler(args: dict) -> tuple[str, bool]:
    """Handler returns (output_text, is_error)."""
    try:
        # ... 实现逻辑 ...
        return result, False
    except Exception as e:
        return f"Error: {e}", True
```

## 报告 Bug

使用 Issue 模板，包含：
- 复现步骤
- 预期行为 vs 实际行为
- 错误日志（如有）
- 环境信息（OS、Python 版本、求解器版本）

## 行为准则

- 尊重所有参与者
- 聚焦技术讨论
- 接受建设性反馈
