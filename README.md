# OR-Intern

An AI agent for Operations Research — autonomously models, solves, validates, and reports on optimization problems.

**English | [中文](README.zh.md)**

## Quick Start

```bash
# Clone and install
cd or-intern
uv sync

# Set up API keys (LiteLLM compatible)
cp .env.example .env
# Edit .env to add OPENAI_API_KEY

# Configure (optional)
cp config.example.yaml config.yaml

# Interactive mode
uv run or-intern

# Headless mode
uv run or-intern "Solve: maximize 3x+2y s.t. x+y<=10, x>=0, y>=0"
```

## Architecture

```
User Input → Agent Loop → LLM (qwen/claude/gpt via LiteLLM)
                    ↓
              Tool Router (20 tools)
                    ↓
    ┌── Infrastructure ──┬── OR Core ──────┬── Analysis ──────┐
    │ bash, read, write, │ model_builder,   │ sensitivity,     │
    │ edit, plan_tool,   │ solver_selector, │ visualization,   │
    │ notify_tool        │ solve_job,       │ report_gen,      │
    │                    │ validate_solution,│ compare_solvers  │
    │                    │ cvxpy_builder,   │                  │
    │                    │ robust_builder,  │                  │
    │                    │ stochastic_builder│                  │
    │                    │ problem_templates│                  │
    │                    │ model_checker,   │                  │
    │                    │ or_papers,       │                  │
    │                    │ data_handler     │                  │
    └─────────────────────┴────────────────┴──────────────────┘
```

## Configuration

Copy `config.example.yaml` to `config.yaml` and customize:

```bash
cp config.example.yaml config.yaml
```

Example configuration:

```yaml
model:
  name: openai/qwen3.6-plus
  api_base: ""  # or https://your-endpoint/v1
  reasoning_effort: high
  max_iterations: 500

solver:
  default: highs
  timeout: 3600

session:
  save: true
  auto_save_interval: 1
  log_dir: session_logs
  heartbeat_interval: 60

approval:
  yolo_mode: false
  cost_cap_usd: 1.0
  confirm_expensive: true

tool_runtime: local
mcp_servers: {}

messaging:
  enabled: false
  auto_event_types: [approval_required, error, turn_complete]
  destinations: {}
```

Environment variables can be referenced in config.yaml using `$VAR`, `${VAR}`, or `${VAR:-default}` syntax.
Secrets should go in `.env` (see `.env.example`):

```bash
# .env — only secrets, no configuration
OPENAI_API_KEY=sk-your-key-here
# ANTHROPIC_API_KEY=your-key
# SLACK_BOT_TOKEN=xoxb-your-token
```

Config file search order:
1. `OR_INTERN_CONFIG` environment variable (explicit path)
2. `./config.yaml` (current directory)
3. `~/.config/or-intern/config.yaml` (user config directory)

## Testing

```bash
uv run pytest tests/ -v
# 477 tests across unit + integration + benchmarks + regression
```

## Project Structure

```
or-intern/
├── agent/
│   ├── main.py              # CLI entry point
│   ├── config.py            # Configuration (nested YAML)
│   ├── core/                # Agent engine
│   │   ├── agent_loop.py    # Main agent loop
│   │   ├── approval_policy.py # OR approval rules
│   │   ├── llm_params.py    # LiteLLM integration
│   │   ├── telemetry.py     # Session telemetry & workspace tracking
│   │   ├── session_resume.py # Session restore from log
│   │   └── ...
│   ├── context_manager/     # Context compaction + workspace injection
│   ├── messaging/           # Notification subsystem (Slack, etc.)
│   ├── tools/               # 20 tool implementations
│   │   ├── model_builder.py
│   │   ├── solve_job.py
│   │   ├── _output_dir.py   # Workspace directory management
│   │   └── ...
│   └── prompts/             # System prompts (YAML/Jinja2)
├── config.example.yaml      # Configuration template
├── .env.example             # Secrets template
├── tests/                   # Unit + integration + regression tests
├── outputs/                 # Per-session workspace (gitignored)
├── session_logs/            # Session trajectories (gitignored)
├── pyproject.toml
└── README.md
```

## Documentation

- [API Documentation](docs/api.md) | [API 文档（中文）](docs/api.zh.md)
- [Building an OR Agent](docs/blog-building-an-or-agent.md) | [构建 OR 智能体（中文）](docs/blog-building-an-or-agent.zh.md)

## License

Apache 2.0
