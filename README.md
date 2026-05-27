# OR-Intern

An AI agent for Operations Research — autonomously models, solves, validates, and reports on optimization problems.

## Quick Start

```bash
# Clone and install
cd or-intern
uv sync

# Set up API keys (LiteLLM compatible)
export OPENAI_API_KEY="your-key"
export OPENAI_API_BASE="https://your-api-endpoint/v1"  # optional

# Interactive mode
uv run or-intern

# Headless mode
uv run or-intern "Solve: maximize 3x+2y s.t. x+y<=10, x>=0, y>=0"
```

## Architecture

```
User Input → Agent Loop → LLM (qwen/claude/gpt via LiteLLM)
                    ↓
              Tool Router (18 tools)
                    ↓
    ┌── Infrastructure ──┬── OR Core ──┬── Analysis ──┐
    │ bash, read, write, │ model_builder,  │ sensitivity, │
    │ edit                │ solver_selector, │ visualization,│
    │                     │ solve_job,       │ report_gen,   │
    │                     │ validate_solution,│ compare_solvers│
    │                     │ or_papers,       │               │
    │                     │ data_handler     │               │
    └─────────────────────┴────────────────┴───────────────┘
```

## Tool Chain

| Phase | Tool | Description |
|:-----:|------|-------------|
| 0 | `bash/read/write/edit` | File system operations |
| 1 | `model_builder` | Natural language → Pyomo model |
| 1 | `solver_selector` | Recommends best solver |
| 1 | `solve_job` | Executes solve (HiGHS/SCIP/...) |
| 1 | `validate_solution` | Constraint verification |
| 1 | `or_papers` | arXiv paper search |
| 1 | `data_handler` | CSV/JSON data loading |
| 1 | `research` | Sub-agent research |
| 2 | `sensitivity_analysis` | Shadow prices + parametric |
| 2 | `visualization` | Charts (bar, gap, sensitivity) |
| 2 | `compare_solvers` | Multi-solver benchmark |
| 2 | `report_generator` | Markdown reports |

## Configuration

Edit `configs/cli_config.json`:

```json
{
    "model_name": "openai/qwen3.6-plus",
    "api_base": "https://your-endpoint/v1",
    "reasoning_effort": null,
    "max_iterations": 500,
    "default_solver": "highs",
    "solver_timeout": 3600,
    "yolo_mode": false,
    "auto_approval_cost_cap_usd": 1.0
}
```

## Testing

```bash
uv run pytest tests/ -v
# 35 tests across 5 test files
```

## Project Structure

```
or-intern/
├── agent/
│   ├── main.py              # CLI entry point
│   ├── config.py            # Configuration
│   ├── core/                # Agent engine
│   │   ├── agent_loop.py    # Main agent loop
│   │   ├── approval_policy.py # OR approval rules
│   │   ├── llm_params.py    # LiteLLM integration
│   │   └── ...
│   ├── context_manager/     # Context compaction
│   ├── tools/               # 18 tool implementations
│   │   ├── model_builder.py
│   │   ├── solve_job.py
│   │   └── ...
│   └── prompts/             # System prompts
├── configs/                 # Default config
├── tests/                   # Unit + integration tests
├── pyproject.toml
└── README.md
```

## License

Apache 2.0
