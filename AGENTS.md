# AGENTS.md — OR-Intern Developer Guide

## Overview

OR-Intern is an AI agent for Operations Research — it can automatically generate mathematical models from natural language descriptions, invoke solvers, verify solutions, perform sensitivity analysis, and produce visualizations and reports.

**Vision**: From description to solution, in a single conversation.

## Architecture

```
User Input → Agent Loop → LLM (qwen/claude/gpt via LiteLLM)
                    ↓
              Tool Router (20 tools)
                    ↓
    ┌── Infrastructure ──┬── OR Core ──────┬── Analysis ──────┐
    │ bash, read, write, │ model_builder,   │ sensitivity,     │
    │ edit, plan_tool,   │ cvxpy_builder,   │ visualization,   │
    │ notify_tool        │ robust_builder,  │ report_gen,      │
    │                    │ stochastic_builder│ compare_solvers  │
    │                    │ problem_templates│                  │
    │                    │ model_checker,   │                  │
    │                    │ solver_selector, │                  │
    │                    │ solve_job,       │                  │
    │                    │ validate_solution,│                  │
    │                    │ or_papers,       │                  │
    │                    │ data_handler     │                  │
    └─────────────────────┴────────────────┴──────────────────┘
```

### Layers

| Layer | Directory | Description |
|-------|-----------|-------------|
| CLI Entry | `agent/main.py` | Interactive + headless modes, with /undo /new /compact /sessions /resume commands |
| Agent Engine | `agent/core/` | agent_loop, session, doom_loop, approval_policy, telemetry, session_resume |
| Context Manager | `agent/context_manager/` | Compaction strategy, solve log summarization, **workspace file listing injection** |
| Tool Layer | `agent/tools/` | 20 tool implementations |
| Messaging | `agent/messaging/` | Notification gateway (Slack, etc.), auto-event push |
| System Prompt | `agent/prompts/system_prompt.yaml` | 6-phase quality gate workflow + workspace hints |
| Config | `config.example.yaml` → `config.yaml` | Nested YAML structure (model/solver/session/approval/messaging) |
| Secrets | `.env.example` → `.env` | API keys only |
| Tests | `tests/` | unit + integration + benchmarks + regression |

## Key Design Decisions

### 1. 6-Phase Quality Gate Workflow

System prompt forces the LLM through all phases:

```
Phase 1: MODEL     → model_builder / cvxpy_builder / robust_builder / stochastic_builder
Phase 2: SOLVE     → solver_selector + solve_job
  ┌── Quality Gate ──┐
  │ OPTIMAL, gap≈0   │→ Continue
  │ gap>5% / slow    │→ Switch solver (max 3 attempts)
  │ INFEASIBLE       │→ Diagnose conflict
  └──────────────────┘
Phase 3: VALIDATE  → validate_solution
Phase 4: ANALYZE   → sensitivity_analysis
Phase 5: VISUALIZE → visualization
Phase 6: REPORT    → report_generator
```

### 2. Session-Scoped Workspace

Each session has a persistent workspace directory `outputs/<session_id[:8]>/`:

- **All tool outputs write to the same directory**, files persist across conversation turns
- LLM can name files via the `filename` parameter (e.g., `model_v2_relaxed.py`)
- If no filename specified, `suggest_filename()` auto-adds version suffixes (`model.py` → `model_v2.py`)
- `.workspace_state.json` auto-records file metadata (type, tool, timestamp, notes)
- `context_manager._inject_workspace_context()` injects the file listing into the system prompt before each turn

Coordination: `agent/tools/_output_dir.py` with `get_workspace_dir(session)` + `record_file()` + `list_workspace_files()`.

### 3. Configuration System (Nested YAML)

Configuration is split into two files with clear responsibilities:

**`config.yaml`** (structured configuration):
```yaml
model:
  name: openai/qwen3.6-plus
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

messaging:
  enabled: false
  auto_event_types: [approval_required, error, turn_complete]
  destinations: {}
```

**`.env`** (secrets only, gitignored):
```bash
OPENAI_API_KEY=sk-your-key-here
# ANTHROPIC_API_KEY=your-key
# SLACK_BOT_TOKEN=xoxb-your-token
```

Config file search order: `OR_INTERN_CONFIG` → `./config.yaml` → `~/.config/or-intern/config.yaml`

YAML supports `$VAR`, `${VAR}`, and `${VAR:-default}` for environment variable references.

Pydantic model structure: `Config` → `ModelConfig` + `SolverConfig` + `SessionConfig` + `ApprovalConfig` + `MessagingConfig`

### 4. Session Restore and Undo

| Command | Function |
|---------|----------|
| `/undo` | Undo last conversation turn (remove last user message + all subsequent assistant/tool messages) |
| `/new` | Start new conversation (save old session, clear context, keep model/config) |
| `/compact` | Manually trigger context compaction (only if above 85% threshold) |
| `/sessions` | List saved sessions in `session_logs/` |
| `/resume <path>` | Restore session from JSON log (rebuild message history + workspace file listing) |

### 5. Solver Integration

Default: HiGHS (open-source, fast). SCIP as fallback. Gurobi/CPLEX require approval.

### 6. Gap/Bound Information

`solve_job` returns Status, Gap, Lower Bound, Upper Bound, Solver Time for Quality Gate decisions.

## Development Environment

```bash
# Install dependencies
cd or-intern
uv sync

# Configure
cp config.example.yaml config.yaml
cp .env.example .env
# Edit .env to add OPENAI_API_KEY

# Run tests
uv run pytest tests/ -v

# Start CLI
uv run or-intern
```

## Adding New Tools

1. Create tool file in `agent/tools/` (e.g., `my_tool.py`)
2. Define `MY_TOOL_SPEC` (JSON Schema) and `my_tool_handler` (async function with `session` parameter)
3. Use `get_workspace_dir(session)` in handler to get workspace directory
4. Register in `agent/core/tools.py` in `create_builtin_tools()`
5. Add description in `agent/prompts/system_prompt.yaml` under Available Tools
6. Add unit tests in `tests/unit/`

## Testing

```bash
# All tests (477)
uv run pytest tests/ -v

# Unit tests only
uv run pytest tests/unit/ -v

# Benchmarks (end-to-end)
uv run pytest tests/benchmarks/ -v

# Regression tests (128 tests, covering 15 dimensions)
uv run pytest tests/benchmarks/test_regression.py -v

# Full pipeline tests only
uv run pytest tests/benchmarks/ -v -k "FullPipeline"
```

## Relationship with ML-Intern

OR-Intern is built on ML-Intern's agent infrastructure (agent_loop, context_manager, doom_loop, etc.), but:
- Removed all HuggingFace-specific code
- Replaced with OR domain toolset (20 tools)
- Rewrote system prompt (6-phase quality gate + workspace awareness)
- Tuned context management (OR compaction strategy, 85% threshold, 10-message tail retention)
- Restructured configuration (nested YAML + Pydantic nested models)
- Added session restore/undo functionality
- Added multi-source paper search (arXiv + Semantic Scholar + OpenAlex)
- Added session-scoped workspace (session = workspace)
