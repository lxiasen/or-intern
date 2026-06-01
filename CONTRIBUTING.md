# Contributing to OR-Intern

Thank you for your interest in contributing to OR-Intern!

## Quick Start

```bash
# 1. Fork and clone the repository
git clone https://github.com/your-username/or-intern.git
cd or-intern

# 2. Install dependencies
uv sync

# 3. Configuration file (structured configuration)
cp config.example.yaml config.yaml
# Edit config.yaml to adjust model, solver, and other settings

# 4. Secrets (API keys only, gitignored)
cp .env.example .env
# Edit .env to add your OPENAI_API_KEY

# 5. Run tests to verify environment
uv run pytest tests/ -v
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Write Code

- Follow existing code style
- For new tools, refer to the "Adding New Tools" guide in `AGENTS.md`
- Tool output files must be written to the session workspace (see specification below)
- Add tests for new features

### 3. Run Tests

```bash
# All tests
uv run pytest tests/ -v

# Specific test file
uv run pytest tests/unit/test_model_builder.py -v

# Regression tests (128 tests, covering 15 dimensions)
uv run pytest tests/benchmarks/test_regression.py -v
```

### 4. Submit PR

- Use clear, descriptive titles for changes
- Link related Issues
- Ensure CI passes

## Code Standards

- **Python 3.12+**, use type hints
- **Async-first**: Tool handlers must be `async def`
- **Error handling**: Tools must return user-friendly error messages, not raise exceptions directly
- **Test coverage**: At least 3 test cases per new tool
- **Config access**: Use nested paths (`config.model.name`, not `config.model_name`)

## Tool Development Specification

```python
from agent.tools._output_dir import get_workspace_dir, suggest_filename, record_file

# 1. Define tool spec (JSON Schema)
MY_TOOL_SPEC = {
    "name": "my_tool",
    "description": "Tool description for LLM",
    "parameters": {
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "..."},
            "filename": {
                "type": "string",
                "description": "Output filename. Auto-versioned if omitted.",
            },
        },
        "required": ["param1"],
    },
}

# 2. Implement handler (async, receives session, returns tuple[str, bool])
async def my_tool_handler(args: dict, session=None) -> tuple[str, bool]:
    """Handler returns (output_text, is_error)."""
    try:
        # Get session workspace
        workspace = get_workspace_dir(session)

        # LLM can specify filename, otherwise auto-versioned
        filename = args.get("filename", "")
        if filename:
            out_path = workspace / filename
        else:
            out_path = workspace / suggest_filename(workspace, "output", ".txt")

        # Write file
        out_path.write_text("result content", encoding="utf-8")

        # Record to workspace state (for context_manager to inject into system prompt)
        record_file(workspace, out_path.name, file_type="output",
                     tool="my_tool", note="Description of what was generated")

        return f"Generated: {out_path}", False
    except Exception as e:
        return f"Error: {e}", True
```

### Workspace Key Points

- Each session has an independent workspace directory `outputs/<session_id[:8]>/`
- Files persist across multiple conversation turns; LLM can reference and modify previous outputs
- `record_file()` automatically updates `.workspace_state.json`
- `context_manager` injects the file list into the system prompt before each conversation turn

## Configuration System

Configuration is split into two files:

| File | Purpose | Gitignored? |
|------|---------|:-----------:|
| `config.yaml` | Structured configuration (model, solver, approval policy, messaging) | Yes |
| `.env` | Sensitive information only (API keys, etc.) | Yes |
| `config.example.yaml` | Configuration template (with comments) | No |
| `.env.example` | Secrets template | No |

YAML supports environment variable references using `$VAR`, `${VAR}`, and `${VAR:-default}` syntax.

Pydantic nested model structure: `Config` → `ModelConfig` + `SolverConfig` + `SessionConfig` + `ApprovalConfig` + `MessagingConfig`

## Reporting Bugs

Use the Issue template, including:
- Steps to reproduce
- Expected behavior vs actual behavior
- Error logs (if any)
- Environment information (OS, Python version, solver version)

## Code of Conduct

- Respect all participants
- Focus on technical discussions
- Accept constructive feedback
