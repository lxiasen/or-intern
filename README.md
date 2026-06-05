# OR-Intern

**An AI agent for Operations Research — from description to solution, in a single conversation.**

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-blue?style=flat-square" alt="Version">
  <img src="https://img.shields.io/badge/python-3.10+-green?style=flat-square" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/tests-477%20passed-brightgreen?style=flat-square" alt="Tests">
  <img src="https://img.shields.io/badge/license-Apache%202.0-yellow?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/PRs-welcome-orange?style=flat-square" alt="PRs Welcome">
</p>

<p align="center">
  <strong>English</strong> | <a href="README.zh.md">中文</a>
</p>

---

## ✨ Highlights

| Feature | Description |
|---------|-------------|
| 🤖 **6-Phase Quality Gate** | Automatic workflow: Model → Solve → Validate → Analyze → Visualize → Report |
| 🔧 **20 Built-in Tools** | model_builder, solver_selector, sensitivity_analysis, visualization, and more |
| 🚀 **Multi-Solver Support** | HiGHS (default), SCIP, Gurobi, CPLEX with automatic fallback |
| 📊 **Rich Outputs** | Generated models (Python/CVXPY), charts, sensitivity reports, PDF reports |
| 💾 **Session Management** | Undo, compact, restore sessions with persistent workspace |
| 🌐 **Multi-LLM Backend** | Supports Qwen, Claude, GPT via LiteLLM |

---

## 🚀 Quick Start

### 1. Install

```bash
git clone https://github.com/your-org/or-intern.git
cd or-intern
uv sync
```

### 2. Configure

```bash
# Copy config templates
cp config.example.yaml config.yaml
cp .env.example .env

# Edit .env to add your API key
# OPENAI_API_KEY=sk-your-key-here
```

### 3. Run

```bash
# Interactive mode
uv run or-intern

# Headless mode (single problem)
uv run or-intern "Solve: maximize 3x+2y s.t. x+y<=10, x>=0, y>=0"
```

---

## 🏗️ Architecture

```mermaid
graph TD
    A[User Input] --> B[Agent Loop]
    B --> C[LLM<br>Qwen/Claude/GPT via LiteLLM]
    C --> D[Tool Router]
    D --> E[Infrastructure Tools]
    D --> F[OR Core Tools]
    D --> G[Analysis Tools]
    
    E --> E1[bash, read, write]
    E --> E2[edit, plan_tool]
    E --> E3[notify_tool]
    
    F --> F1[model_builder]
    F --> F2[cvxpy_builder]
    F --> F3[robust_builder]
    F --> F4[solver_selector]
    F --> F5[solve_job]
    F --> F6[validate_solution]
    F --> F7[problem_templates]
    F --> F8[or_papers]
    F --> F9[data_handler]
    
    G --> G1[sensitivity]
    G --> G2[visualization]
    G --> G3[report_gen]
    G --> G4[compare_solvers]
    
    style A fill:#e1f5ff
    style B fill:#fff3e0
    style C fill:#f3e5f5
    style D fill:#e8f5e8
```

### 6-Phase Quality Gate Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: MODEL    → model_builder / cvxpy_builder / robust    │
├─────────────────────────────────────────────────────────────────┤
│  Phase 2: SOLVE    → solver_selector + solve_job               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ OPTIMAL, gap≈0  → Continue                              │   │
│  │ gap>5% / slow   → Switch solver (max 3 attempts)        │   │
│  │ INFEASIBLE      → Diagnose conflict                     │   │
│  └─────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│  Phase 3: VALIDATE → validate_solution                         │
├─────────────────────────────────────────────────────────────────┤
│  Phase 4: ANALYZE  → sensitivity_analysis                      │
├─────────────────────────────────────────────────────────────────┤
│  Phase 5: VISUALIZE → visualization                            │
├─────────────────────────────────────────────────────────────────┤
│  Phase 6: REPORT   → report_generator                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## ⚙️ Configuration

### Config Files

| File | Purpose | Version Control |
|------|---------|-----------------|
| `config.yaml` | Model, solver, session settings | ✅ Safe to commit |
| `.env` | API keys, secrets only | ❌ Gitignored |

### Example `config.yaml`

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

### Config Search Order

1. `OR_INTERN_CONFIG` environment variable (explicit path)
2. `./config.yaml` (current directory)
3. `~/.config/or-intern/config.yaml` (user config directory)

### Environment Variables

Use `$VAR`, `${VAR}`, or `${VAR:-default}` syntax in config.yaml to reference environment variables.

```bash
# .env — only secrets
OPENAI_API_KEY=sk-your-key-here
# ANTHROPIC_API_KEY=your-key
# SLACK_BOT_TOKEN=xoxb-your-token
```

---

## 📁 Project Structure

```
or-intern/
├── agent/
│   ├── main.py              # CLI entry point (interactive + headless)
│   ├── config.py            # Configuration (nested YAML + Pydantic)
│   ├── core/                # Agent engine
│   │   ├── agent_loop.py    # Main agent loop
│   │   ├── session.py       # Session management
│   │   ├── doom_loop.py     # Infinite loop detection
│   │   └── telemetry.py     # Session telemetry & workspace tracking
│   ├── context_manager/     # Context compaction + workspace injection
│   ├── messaging/           # Notification subsystem (Slack, etc.)
│   ├── tools/               # 20 tool implementations
│   │   ├── model_builder.py # Generate OR models
│   │   ├── solve_job.py     # Execute solvers
│   │   ├── _output_dir.py   # Workspace directory management
│   │   └── ...
│   └── prompts/             # System prompts (YAML/Jinja2)
├── config.example.yaml      # Configuration template
├── .env.example             # Secrets template
├── tests/                   # 477 tests (unit + integration + regression)
├── outputs/                 # Per-session workspace (gitignored)
├── session_logs/            # Session trajectories (gitignored)
├── pyproject.toml
└── README.md
```

---

## 🧪 Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Unit tests only
uv run pytest tests/unit/ -v

# Benchmarks (end-to-end)
uv run pytest tests/benchmarks/ -v

# Regression tests (128 tests, 15 dimensions)
uv run pytest tests/benchmarks/test_regression.py -v

# Full pipeline tests
uv run pytest tests/benchmarks/ -v -k "FullPipeline"
```

---

## 💡 Usage Examples

### Example 1: Simple Linear Programming

```bash
uv run or-intern "Solve: maximize 3x+2y s.t. x+y<=10, x>=0, y>=0"
```

**Output:**
```
## Phase 1: Model
✅ Model generated: maximize 3x + 2y, subject to: x + y <= 10

## Phase 2: Solve
✅ Optimal solution: x = 10, y = 0, objective = 30

## Phase 3-6
[Automatically completes validation, sensitivity analysis, visualization, report]
```

### Example 2: Semiconductor Material Shortage Prediction (Real Business Scenario)

```bash
# Prepare data files (CSV format)
# test_data/materials.csv - Material master data
# test_data/production_plan.csv - Production plan
# test_data/bom.csv - Bill of Materials

uv run or-intern "Analyze material shortage risk for semiconductor manufacturing. Data files are in test_data/ directory"
```

**System automatically completes:**
1. **Data Loading** - Read CSV files (materials, BOM, production plan)
2. **Model Building** - Generate MRP optimization model (Pyomo)
3. **Solving** - Use HiGHS solver to identify shortage risks
4. **Validation** - Verify constraint satisfaction
5. **Visualization** - Generate inventory trend charts, risk heatmaps, reorder suggestions
6. **Report Generation** - Output complete analysis report

**Output Files:**
```
outputs/2026-06-04_xxxxxxxx/
├── report.md                    # Complete analysis report
├── material_shortage_model.py   # MRP optimization model
├── shortage_analysis_result.json # Analysis result data
├── inventory_trend.png          # Inventory trend chart
├── shortage_heatmap.png         # Shortage risk heatmap
├── reorder_suggestions.png      # Reorder suggestions chart
└── supplier_pie.png             # Supplier cost distribution
```

**Analysis Summary:**
| Priority | Material | Reorder Qty | Latest Order | Cost |
|:--------:|:---------|:-----------:|:------------:|:----:|
| Urgent | Silicon Wafer | 6,660 | Week 1 | $169,830 |
| Urgent | Metal Target | 618 | Week 1 | $27,810 |
| Important | Etching Gas | 2,756 | Week 2 | $23,426 |

### Example 3: Using Paper Search (Complex Problems)

```bash
uv run or-intern "I want to use distributionally robust optimization to handle 
demand uncertainty in supply chain. First search for relevant papers, then 
build and solve the model."
```

**System will:**
1. Use `or_papers` to search arXiv for relevant papers
2. Use `research` sub-agent for in-depth study
3. Use `stochastic_builder` to build stochastic programming model
4. Complete the full 6-phase workflow

---

## 📚 Documentation

- [API Documentation](docs/api.md) | [API 文档（中文）](docs/api.zh.md)
- [Building an OR Agent](docs/blog-building-an-or-agent.md) | [构建 OR 智能体（中文）](docs/blog-building-an-or-agent.zh.md)

---

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

1. **Report Bugs** - Open an issue with reproduction steps
2. **Suggest Features** - Share your ideas in discussions
3. **Submit PRs** - Fork, branch, and submit your changes
4. **Improve Docs** - Help make documentation clearer

### Adding New Tools

1. Create tool file in `agent/tools/` (e.g., `my_tool.py`)
2. Define `MY_TOOL_SPEC` (JSON Schema) and `my_tool_handler` (async function)
3. Use `get_workspace_dir(session)` to get workspace directory
4. Register in `agent/core/tools.py` in `create_builtin_tools()`
5. Add description in `agent/prompts/system_prompt.yaml`
6. Add unit tests in `tests/unit/`

---

## 📄 License

Apache 2.0 - See [LICENSE](LICENSE) for details.

---

<p align="center">
  Made with ❤️ by the OR-Intern Team
</p>
